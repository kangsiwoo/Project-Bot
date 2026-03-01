"""Claude Code CLI subprocess 실행 모듈"""

import asyncio
from dataclasses import dataclass


DEFAULT_TIMEOUT = 120  # 초


@dataclass
class ClaudeResponse:
    """Claude Code CLI 실행 결과"""

    text: str
    session_id: str | None
    success: bool
    error: str | None = None


class ClaudeCodeClient:
    """Claude Code CLI를 subprocess로 실행하여 AI 응답을 생성한다."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    async def send_message(
        self, user_message: str, session_id: str | None = None
    ) -> ClaudeResponse:
        """Claude Code CLI를 실행하여 AI 응답을 반환한다.

        Args:
            user_message: 유저 메시지
            session_id: 이전 세션 ID (--resume 용)

        Returns:
            ClaudeResponse: CLI 실행 결과
        """
        cmd = ["claude", "-p", user_message]

        if session_id:
            cmd.extend(["--resume", session_id])

        try:
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
                session_id=session_id,
                success=False,
                error=f"Claude Code 응답 시간 초과 ({self.timeout}초)",
            )
        except FileNotFoundError:
            return ClaudeResponse(
                text="",
                session_id=session_id,
                success=False,
                error="Claude Code CLI를 찾을 수 없습니다. 설치를 확인해주세요.",
            )

        if process.returncode != 0:
            error_msg = stderr.decode().strip() or "알 수 없는 오류"
            return ClaudeResponse(
                text="",
                session_id=session_id,
                success=False,
                error=f"Claude Code 오류: {error_msg}",
            )

        output = stdout.decode().strip()

        # --resume 으로 새 세션이 시작되면 session_id를 갱신할 수 있으나
        # 현재 CLI는 session_id를 stdout에 포함하지 않으므로 기존 값 유지
        return ClaudeResponse(
            text=output,
            session_id=session_id,
            success=True,
        )
