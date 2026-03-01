"""on_message 이벤트 핸들러 단위 테스트"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

from claude_code_client import ClaudeResponse


def make_mock_message(content, author_bot=False, channel_name="bot-console-alice"):
    msg = MagicMock()
    msg.content = content
    msg.author = MagicMock()
    msg.author.bot = author_bot
    msg.author.id = 111222333
    msg.channel = MagicMock()
    msg.channel.name = channel_name
    msg.channel.send = AsyncMock()
    msg.channel.typing = MagicMock(return_value=AsyncContextManager())
    return msg


class AsyncContextManager:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestOnMessage:
    def _run(self, coro):
        return asyncio.run(coro)

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_responds_in_bot_console(self, mock_sm, mock_claude):
        """bot-console 채널에서 AI 응답을 전송한다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(
                text="안녕하세요!", session_id="s1", success=True
            )
        )

        msg = make_mock_message("안녕")
        from server import on_message

        self._run(on_message(msg))

        mock_claude.send_message.assert_called_once_with("안녕", session_id=None)
        msg.channel.send.assert_called_once_with("안녕하세요!")
        session.add_message.assert_any_call("user", "안녕")
        session.add_message.assert_any_call("assistant", "안녕하세요!")

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_ignores_bot_message(self, mock_sm, mock_claude):
        """봇 자신의 메시지는 무시한다"""
        msg = make_mock_message("test", author_bot=True)
        from server import on_message

        self._run(on_message(msg))

        mock_claude.send_message.assert_not_called()
        mock_sm.get_or_create_session.assert_not_called()

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_ignores_non_console_channel(self, mock_sm, mock_claude):
        """bot-console이 아닌 채널은 무시한다"""
        msg = make_mock_message("test", channel_name="general")
        from server import on_message

        self._run(on_message(msg))

        mock_claude.send_message.assert_not_called()
        mock_sm.get_or_create_session.assert_not_called()

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_error_response(self, mock_sm, mock_claude):
        """CLI 에러 시 에러 메시지를 전송한다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(
                text="", session_id=None, success=False, error="타임아웃"
            )
        )

        msg = make_mock_message("테스트")
        from server import on_message

        self._run(on_message(msg))

        msg.channel.send.assert_called_once()
        sent = msg.channel.send.call_args.args[0]
        assert "타임아웃" in sent

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_long_response_chunked(self, mock_sm, mock_claude):
        """2000자 초과 응답은 청크 분할하여 전송한다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        long_text = "A" * 4500
        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(
                text=long_text, session_id=None, success=True
            )
        )

        msg = make_mock_message("long")
        from server import on_message

        self._run(on_message(msg))

        assert msg.channel.send.call_count == 3
        chunks = [call.args[0] for call in msg.channel.send.call_args_list]
        assert len(chunks[0]) == 2000
        assert len(chunks[1]) == 2000
        assert len(chunks[2]) == 500

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_session_id_updated(self, mock_sm, mock_claude):
        """응답의 session_id로 세션을 갱신한다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(
                text="응답", session_id="new-session-123", success=True
            )
        )

        msg = make_mock_message("테스트")
        from server import on_message

        self._run(on_message(msg))

        assert session.session_id == "new-session-123"

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_resumes_existing_session(self, mock_sm, mock_claude):
        """기존 세션이 있으면 resume한다"""
        session = MagicMock()
        session.session_id = "existing-session"
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(
                text="이어서 응답", session_id="existing-session", success=True
            )
        )

        msg = make_mock_message("이어서")
        from server import on_message

        self._run(on_message(msg))

        mock_claude.send_message.assert_called_once_with(
            "이어서", session_id="existing-session"
        )
