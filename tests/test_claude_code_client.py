"""claude_code_client 단위 테스트"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from claude_code_client import (
    ClaudeCodeClient,
    ClaudeResponse,
    StreamEvent,
    parse_stream_event,
    DEFAULT_TIMEOUT,
)


class TestClaudeCodeClient:
    def _run(self, coro):
        return asyncio.run(coro)

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_send_message_success(self, mock_exec):
        """정상 응답을 반환한다"""
        process = AsyncMock()
        process.communicate.return_value = (b"Hello from Claude", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        result = self._run(client.send_message("안녕하세요"))

        assert result.success is True
        assert result.text == "Hello from Claude"
        assert result.error is None

        cmd = mock_exec.call_args.args
        assert "claude" in cmd
        assert "-p" in cmd
        assert "안녕하세요" in cmd

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_send_message_with_session(self, mock_exec):
        """session_id가 있으면 --resume 옵션을 추가한다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        result = self._run(client.send_message("테스트", session_id="abc-123"))

        assert result.success is True
        assert result.session_id == "abc-123"

        cmd = mock_exec.call_args.args
        assert "--resume" in cmd
        assert "abc-123" in cmd

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_send_message_without_session(self, mock_exec):
        """session_id가 없으면 --resume 옵션을 추가하지 않는다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        self._run(client.send_message("테스트"))

        cmd = mock_exec.call_args.args
        assert "--resume" not in cmd

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_nonzero_exit_code(self, mock_exec):
        """CLI가 비정상 종료하면 에러를 반환한다"""
        process = AsyncMock()
        process.communicate.return_value = (b"", b"error occurred")
        process.returncode = 1
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        result = self._run(client.send_message("테스트"))

        assert result.success is False
        assert "error occurred" in result.error

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_nonzero_exit_no_stderr(self, mock_exec):
        """stderr 없이 비정상 종료하면 알 수 없는 오류를 반환한다"""
        process = AsyncMock()
        process.communicate.return_value = (b"", b"")
        process.returncode = 1
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        result = self._run(client.send_message("테스트"))

        assert result.success is False
        assert "알 수 없는 오류" in result.error

    @patch("claude_code_client.asyncio.wait_for", side_effect=asyncio.TimeoutError)
    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_timeout(self, mock_exec, mock_wait_for):
        """타임아웃 시 에러를 반환한다"""
        process = AsyncMock()
        process.kill = MagicMock()
        process.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = process

        client = ClaudeCodeClient(timeout=5)
        result = self._run(client.send_message("테스트"))

        assert result.success is False
        assert "시간 초과" in result.error
        process.kill.assert_called_once()

    @patch(
        "claude_code_client.asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError,
    )
    def test_cli_not_found(self, mock_exec):
        """claude CLI가 없으면 에러를 반환한다"""
        client = ClaudeCodeClient()
        result = self._run(client.send_message("테스트"))

        assert result.success is False
        assert "찾을 수 없습니다" in result.error

    def test_default_timeout(self):
        """기본 타임아웃은 120초이다"""
        client = ClaudeCodeClient()
        assert client.timeout == DEFAULT_TIMEOUT
        assert client.timeout == 120

    def test_custom_timeout(self):
        """커스텀 타임아웃을 설정할 수 있다"""
        client = ClaudeCodeClient(timeout=30)
        assert client.timeout == 30

    def test_claude_response_dataclass(self):
        """ClaudeResponse 데이터 클래스가 정상 동작한다"""
        resp = ClaudeResponse(text="hello", session_id="s1", success=True)
        assert resp.text == "hello"
        assert resp.session_id == "s1"
        assert resp.success is True
        assert resp.error is None

        resp_err = ClaudeResponse(
            text="", session_id=None, success=False, error="오류"
        )
        assert resp_err.error == "오류"


# ---------------------------------------------------------------------------
# parse_stream_event 테스트
# ---------------------------------------------------------------------------


class TestParseStreamEvent:
    def test_system_event(self):
        """system 이벤트를 파싱한다"""
        line = json.dumps(
            {"type": "system", "subtype": "init", "session_id": "sess-1"}
        )
        event = parse_stream_event(line)
        assert event.event_type == "system"
        assert event.session_id == "sess-1"

    def test_assistant_event(self):
        """assistant 이벤트에서 텍스트를 추출한다"""
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "안녕하세요!"}]
                },
                "session_id": "sess-1",
            }
        )
        event = parse_stream_event(line)
        assert event.event_type == "assistant"
        assert event.text == "안녕하세요!"
        assert event.session_id == "sess-1"

    def test_assistant_multiple_text_blocks(self):
        """여러 텍스트 블록을 합친다"""
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "World"},
                    ]
                },
            }
        )
        event = parse_stream_event(line)
        assert event.text == "Hello World"

    def test_assistant_non_text_blocks_ignored(self):
        """텍스트가 아닌 블록은 무시한다"""
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Read"},
                        {"type": "text", "text": "결과입니다"},
                    ]
                },
            }
        )
        event = parse_stream_event(line)
        assert event.text == "결과입니다"

    def test_result_event(self):
        """result 이벤트를 파싱한다"""
        line = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "result": "최종 응답",
                "session_id": "sess-1",
            }
        )
        event = parse_stream_event(line)
        assert event.event_type == "result"
        assert event.text == "최종 응답"
        assert event.session_id == "sess-1"

    def test_empty_line(self):
        """빈 줄은 None을 반환한다"""
        assert parse_stream_event("") is None
        assert parse_stream_event("  ") is None

    def test_invalid_json(self):
        """잘못된 JSON은 None을 반환한다"""
        assert parse_stream_event("not json") is None

    def test_unknown_type(self):
        """알 수 없는 타입도 파싱한다"""
        line = json.dumps({"type": "unknown_event", "data": 123})
        event = parse_stream_event(line)
        assert event.event_type == "unknown_event"


# ---------------------------------------------------------------------------
# stream_message 테스트
# ---------------------------------------------------------------------------


class TestStreamMessage:
    def _run(self, coro):
        return asyncio.run(coro)

    async def _collect_events(self, async_gen) -> list[StreamEvent]:
        events = []
        async for event in async_gen:
            events.append(event)
        return events

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_stream_success(self, mock_exec):
        """스트리밍으로 이벤트를 순서대로 yield한다"""
        system_line = json.dumps(
            {"type": "system", "session_id": "s1"}
        )
        assistant_line = json.dumps(
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "응답"}]},
                "session_id": "s1",
            }
        )
        result_line = json.dumps(
            {"type": "result", "result": "응답", "session_id": "s1"}
        )

        lines = [
            system_line.encode() + b"\n",
            assistant_line.encode() + b"\n",
            result_line.encode() + b"\n",
        ]

        async def mock_readline():
            for line in lines:
                yield line
            yield b""

        process = MagicMock()
        process.stdout = MagicMock()
        readline_gen = mock_readline()
        process.stdout.readline = lambda: readline_gen.__anext__()
        process.stderr = MagicMock()
        process.stderr.read = AsyncMock(return_value=b"")
        process.wait = AsyncMock(return_value=0)
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        events = self._run(self._collect_events(client.stream_message("테스트")))

        assert len(events) == 3
        assert events[0].event_type == "system"
        assert events[0].session_id == "s1"
        assert events[1].event_type == "assistant"
        assert events[1].text == "응답"
        assert events[2].event_type == "result"
        assert events[2].text == "응답"

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_stream_with_session(self, mock_exec):
        """스트리밍 시 --resume 및 stream-json 플래그를 포함한다"""
        async def empty_readline():
            yield b""

        process = MagicMock()
        process.stdout = MagicMock()
        gen = empty_readline()
        process.stdout.readline = lambda: gen.__anext__()
        process.stderr = MagicMock()
        process.stderr.read = AsyncMock(return_value=b"")
        process.wait = AsyncMock(return_value=0)
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        self._run(self._collect_events(
            client.stream_message("테스트", session_id="abc")
        ))

        cmd = mock_exec.call_args.args
        assert "--resume" in cmd
        assert "abc" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--verbose" in cmd

    @patch(
        "claude_code_client.asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError,
    )
    def test_stream_cli_not_found(self, mock_exec):
        """스트리밍 시 CLI가 없으면 에러 이벤트를 yield한다"""
        client = ClaudeCodeClient()
        events = self._run(self._collect_events(client.stream_message("테스트")))

        assert len(events) == 1
        assert events[0].event_type == "error"
        assert "찾을 수 없습니다" in events[0].text

    def test_stream_event_dataclass(self):
        """StreamEvent 데이터 클래스가 정상 동작한다"""
        event = StreamEvent(event_type="assistant", text="hello", session_id="s1")
        assert event.event_type == "assistant"
        assert event.text == "hello"
        assert event.session_id == "s1"
        assert event.raw == {}

    def test_build_cmd_stream(self):
        """stream=True일 때 올바른 명령어를 생성한다"""
        client = ClaudeCodeClient()
        cmd = client._build_cmd("msg", session_id="s1", stream=True)
        assert cmd == [
            "claude", "-p", "msg", "--resume", "s1",
            "--output-format", "stream-json", "--verbose",
        ]

    def test_build_cmd_no_stream(self):
        """stream=False일 때 기존 명령어를 생성한다"""
        client = ClaudeCodeClient()
        cmd = client._build_cmd("msg", session_id=None, stream=False)
        assert cmd == ["claude", "-p", "msg"]
