"""Claude Code CLI subprocess 실행 모듈"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import AsyncGenerator


DEFAULT_TIMEOUT = 120  # 초


@dataclass
class ClaudeResponse:
    """Claude Code CLI 실행 결과"""

    text: str
    session_id: str | None
    success: bool
    error: str | None = None


@dataclass
class StreamEvent:
    """스트리밍 JSON 이벤트"""

    event_type: str  # "system", "assistant", "result"
    text: str = ""
    session_id: str | None = None
    raw: dict = field(default_factory=dict)


def parse_stream_event(line: str) -> StreamEvent | None:
    """JSON 라인을 StreamEvent로 파싱한다."""
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    event_type = data.get("type", "")

    if event_type == "system":
        return StreamEvent(
            event_type="system",
            session_id=data.get("session_id"),
            raw=data,
        )
    elif event_type == "assistant":
        msg = data.get("message", {})
        content_blocks = msg.get("content", [])
        text_parts = [
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        ]
        return StreamEvent(
            event_type="assistant",
            text="".join(text_parts),
            session_id=data.get("session_id"),
            raw=data,
        )
    elif event_type == "result":
        return StreamEvent(
            event_type="result",
            text=data.get("result", ""),
            session_id=data.get("session_id"),
            raw=data,
        )
    else:
        return StreamEvent(event_type=event_type, raw=data)


class ClaudeCodeClient:
    """Claude Code CLI를 subprocess로 실행하여 AI 응답을 생성한다."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    def _build_cmd(
        self, user_message: str, session_id: str | None, stream: bool
    ) -> list[str]:
        cmd = ["claude", "-p", user_message]
        if session_id:
            cmd.extend(["--resume", session_id])
        if stream:
            cmd.extend(["--output-format", "stream-json", "--verbose"])
        return cmd

    async def send_message(
        self, user_message: str, session_id: str | None = None
    ) -> ClaudeResponse:
        """Claude Code CLI를 실행하여 AI 응답을 반환한다 (단발성).

        Args:
            user_message: 유저 메시지
            session_id: 이전 세션 ID (--resume 용)

        Returns:
            ClaudeResponse: CLI 실행 결과
        """
        cmd = self._build_cmd(user_message, session_id, stream=False)

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
        return ClaudeResponse(
            text=output,
            session_id=session_id,
            success=True,
        )

    async def stream_message(
        self, user_message: str, session_id: str | None = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Claude Code CLI를 스트리밍으로 실행하여 이벤트를 yield한다.

        Args:
            user_message: 유저 메시지
            session_id: 이전 세션 ID (--resume 용)

        Yields:
            StreamEvent: 파싱된 스트리밍 이벤트
        """
        cmd = self._build_cmd(user_message, session_id, stream=True)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            yield StreamEvent(
                event_type="error",
                text="Claude Code CLI를 찾을 수 없습니다. 설치를 확인해주세요.",
            )
            return

        try:
            async def read_lines():
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    yield line.decode()

            async for line in read_lines():
                event = parse_stream_event(line)
                if event:
                    yield event

            await asyncio.wait_for(process.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            yield StreamEvent(
                event_type="error",
                text=f"Claude Code 응답 시간 초과 ({self.timeout}초)",
            )
            return

        if process.returncode != 0:
            stderr_output = await process.stderr.read()
            error_msg = stderr_output.decode().strip() or "알 수 없는 오류"
            yield StreamEvent(
                event_type="error",
                text=f"Claude Code 오류: {error_msg}",
            )
