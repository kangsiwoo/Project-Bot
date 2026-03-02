"""Claude Code CLI subprocess 실행 모듈"""

from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass


DEFAULT_TIMEOUT = 300  # 초

MCP_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp-config.json")

ALLOWED_TOOLS = [
    "mcp__project-bot__create_project",
    "mcp__project-bot__add_team",
    "mcp__project-bot__add_channel",
    "mcp__project-bot__delete_project",
    "mcp__project-bot__list_projects",
    "mcp__project-bot__send_notification",
    "mcp__project-bot__send_message",
    "mcp__project-bot__read_messages",
]


@dataclass
class ClaudeResponse:
    """Claude Code CLI 실행 결과"""

    text: str
    success: bool
    error: str | None = None


class ClaudeCodeClient:
    """Claude Code CLI를 subprocess로 실행하여 AI 응답을 생성한다."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, model: str = "sonnet"):
        self.timeout = timeout
        self.model = model

    async def send_message(
        self,
        user_message: str,
        context_messages: list[dict[str, str]] | None = None,
    ) -> ClaudeResponse:
        """Claude Code CLI를 실행하여 AI 응답을 반환한다.

        Args:
            user_message: 유저 메시지
            context_messages: 이전 대화 컨텍스트 메시지 목록

        Returns:
            ClaudeResponse: CLI 실행 결과
        """
        cmd = [
            "claude", "-p",
            "--model", self.model,
            "--allowedTools", ",".join(ALLOWED_TOOLS),
            "--mcp-config", MCP_CONFIG_PATH,
            "--strict-mcp-config",
        ]

        context_file = None
        try:
            if context_messages:
                context = "\n".join(
                    [f"{m['role']}: {m['content']}" for m in context_messages]
                )
                context_file = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                )
                context_file.write(f"이전 대화 컨텍스트:\n{context}")
                context_file.close()
                cmd.extend(["--append-system-prompt-file", context_file.name])

            cmd.append(user_message)  # 쿼리는 항상 맨 마지막

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return ClaudeResponse(
                text="",
                success=False,
                error=f"Claude Code 응답 시간 초과 ({self.timeout}초)",
            )
        except FileNotFoundError:
            return ClaudeResponse(
                text="",
                success=False,
                error="Claude Code CLI를 찾을 수 없습니다. 설치를 확인해주세요.",
            )
        finally:
            if context_file:
                os.unlink(context_file.name)

        if process.returncode != 0:
            error_msg = stderr.decode().strip() or "알 수 없는 오류"
            return ClaudeResponse(
                text="",
                success=False,
                error=f"Claude Code 오류: {error_msg}",
            )

        output = stdout.decode().strip()
        return ClaudeResponse(
            text=output,
            success=True,
        )
