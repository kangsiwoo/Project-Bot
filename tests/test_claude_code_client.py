"""claude_code_client 단위 테스트"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from claude_code_client import ClaudeCodeClient, ClaudeResponse, DEFAULT_TIMEOUT


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
