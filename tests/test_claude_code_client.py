"""claude_code_client 단위 테스트"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

from claude_code_client import (
    ClaudeCodeClient,
    ClaudeResponse,
    DEFAULT_TIMEOUT,
    ALLOWED_TOOLS,
    MCP_CONFIG_PATH,
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

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_cmd_includes_model_flag(self, mock_exec):
        """--model 플래그가 포함된다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        self._run(client.send_message("테스트"))

        cmd = mock_exec.call_args.args
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "sonnet"

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_cmd_includes_mcp_config(self, mock_exec):
        """--mcp-config과 --strict-mcp-config 플래그가 포함된다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        self._run(client.send_message("테스트"))

        cmd = mock_exec.call_args.args
        assert "--mcp-config" in cmd
        assert "--strict-mcp-config" in cmd
        idx = cmd.index("--mcp-config")
        assert cmd[idx + 1] == MCP_CONFIG_PATH

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_allowed_tools_comma_separated(self, mock_exec):
        """--allowedTools가 쉼표로 구분된 8개 도구를 포함한다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        self._run(client.send_message("테스트"))

        cmd = mock_exec.call_args.args
        assert "--allowedTools" in cmd
        idx = cmd.index("--allowedTools")
        tools_arg = cmd[idx + 1]
        assert tools_arg == ",".join(ALLOWED_TOOLS)
        assert len(tools_arg.split(",")) == 8

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_user_message_is_last_arg(self, mock_exec):
        """user_message가 cmd의 맨 마지막 인자이다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        self._run(client.send_message("마지막 인자 테스트"))

        cmd = mock_exec.call_args.args
        assert cmd[-1] == "마지막 인자 테스트"

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_context_messages_adds_system_prompt_file(self, mock_exec):
        """context_messages가 있으면 --append-system-prompt-file을 추가한다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        context = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
        ]
        self._run(client.send_message("새 질문", context_messages=context))

        cmd = mock_exec.call_args.args
        assert "--append-system-prompt-file" in cmd
        # 쿼리는 여전히 맨 마지막
        assert cmd[-1] == "새 질문"

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_no_context_no_system_prompt_file(self, mock_exec):
        """context_messages가 없으면 --append-system-prompt-file을 추가하지 않는다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        self._run(client.send_message("질문"))

        cmd = mock_exec.call_args.args
        assert "--append-system-prompt-file" not in cmd

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_tempfile_cleaned_up_after_success(self, mock_exec):
        """성공 시 tempfile이 삭제된다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        context = [{"role": "user", "content": "test"}]
        self._run(client.send_message("질문", context_messages=context))

        cmd = mock_exec.call_args.args
        idx = cmd.index("--append-system-prompt-file")
        temp_path = cmd[idx + 1]
        assert not os.path.exists(temp_path)

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_tempfile_cleaned_up_after_error(self, mock_exec):
        """에러 시에도 tempfile이 삭제된다"""
        process = AsyncMock()
        process.communicate.return_value = (b"", b"error")
        process.returncode = 1
        mock_exec.return_value = process

        client = ClaudeCodeClient()
        context = [{"role": "user", "content": "test"}]
        self._run(client.send_message("질문", context_messages=context))

        cmd = mock_exec.call_args.args
        idx = cmd.index("--append-system-prompt-file")
        temp_path = cmd[idx + 1]
        assert not os.path.exists(temp_path)

    @patch("claude_code_client.asyncio.create_subprocess_exec")
    def test_custom_model(self, mock_exec):
        """커스텀 모델을 설정할 수 있다"""
        process = AsyncMock()
        process.communicate.return_value = (b"response", b"")
        process.returncode = 0
        mock_exec.return_value = process

        client = ClaudeCodeClient(model="opus")
        self._run(client.send_message("테스트"))

        cmd = mock_exec.call_args.args
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "opus"

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

    def test_default_timeout_is_300(self):
        """기본 타임아웃은 300초이다"""
        client = ClaudeCodeClient()
        assert client.timeout == DEFAULT_TIMEOUT
        assert client.timeout == 300

    def test_custom_timeout(self):
        """커스텀 타임아웃을 설정할 수 있다"""
        client = ClaudeCodeClient(timeout=30)
        assert client.timeout == 30

    def test_default_model_is_sonnet(self):
        """기본 모델은 sonnet이다"""
        client = ClaudeCodeClient()
        assert client.model == "sonnet"

    def test_claude_response_dataclass(self):
        """ClaudeResponse 데이터 클래스가 정상 동작한다"""
        resp = ClaudeResponse(text="hello", success=True)
        assert resp.text == "hello"
        assert resp.success is True
        assert resp.error is None

        resp_err = ClaudeResponse(text="", success=False, error="오류")
        assert resp_err.error == "오류"

    def test_allowed_tools_has_8_entries(self):
        """ALLOWED_TOOLS에 8개 도구가 정의되어 있다"""
        assert len(ALLOWED_TOOLS) == 8
        assert all(t.startswith("mcp__project-bot__") for t in ALLOWED_TOOLS)

    def test_mcp_config_path_is_absolute(self):
        """MCP_CONFIG_PATH가 절대 경로이다"""
        assert os.path.isabs(MCP_CONFIG_PATH)
        assert MCP_CONFIG_PATH.endswith("mcp-config.json")
