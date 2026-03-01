"""on_message 이벤트 핸들러 단위 테스트 (스트리밍 방식)"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

from claude_code_client import StreamEvent


async def async_stream(*events):
    """StreamEvent 리스트를 async generator로 변환한다."""
    for event in events:
        yield event


def make_mock_channel(name="bot-console-alice"):
    """DiscordStreamHandler와 호환되는 mock 채널을 생성한다."""
    ch = MagicMock()
    ch.name = name
    sent_messages = []

    async def mock_send(content):
        msg = MagicMock()
        msg.content = content
        msg.edit = AsyncMock(
            side_effect=lambda content: setattr(msg, "content", content)
        )
        sent_messages.append(msg)
        return msg

    ch.send = AsyncMock(side_effect=mock_send)
    ch._sent = sent_messages
    return ch


def make_mock_message(content, author_bot=False, channel=None):
    msg = MagicMock()
    msg.content = content
    msg.author = MagicMock()
    msg.author.bot = author_bot
    msg.author.id = 111222333
    msg.channel = channel or make_mock_channel()
    return msg


class TestOnMessage:
    def _run(self, coro):
        return asyncio.run(coro)

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_responds_in_bot_console(self, mock_sm, mock_claude):
        """bot-console 채널에서 AI 스트리밍 응답을 전송한다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        mock_claude.stream_message = MagicMock(
            return_value=async_stream(
                StreamEvent(event_type="system", session_id="s1"),
                StreamEvent(event_type="assistant", text="안녕하세요!"),
                StreamEvent(event_type="result", text="", session_id="s1"),
            )
        )

        ch = make_mock_channel()
        msg = make_mock_message("안녕", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        mock_claude.stream_message.assert_called_once_with("안녕", session_id=None)
        assert ch.send.call_count >= 1
        session.add_message.assert_any_call("user", "안녕")
        session.add_message.assert_any_call("assistant", "안녕하세요!")

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_ignores_bot_message(self, mock_sm, mock_claude):
        """봇 자신의 메시지는 무시한다"""
        msg = make_mock_message("test", author_bot=True)
        from server import on_message

        self._run(on_message(msg))

        mock_claude.stream_message.assert_not_called()
        mock_sm.get_or_create_session.assert_not_called()

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_ignores_non_console_channel(self, mock_sm, mock_claude):
        """bot-console이 아닌 채널은 무시한다"""
        ch = make_mock_channel(name="general")
        msg = make_mock_message("test", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        mock_claude.stream_message.assert_not_called()
        mock_sm.get_or_create_session.assert_not_called()

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_error_response(self, mock_sm, mock_claude):
        """스트리밍 에러 시 경고 메시지를 전송한다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        mock_claude.stream_message = MagicMock(
            return_value=async_stream(
                StreamEvent(event_type="error", text="타임아웃"),
            )
        )

        ch = make_mock_channel()
        msg = make_mock_message("테스트", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        assert ch.send.call_count >= 1
        sent_content = ch._sent[0].content
        assert "타임아웃" in sent_content

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_long_response_chunked(self, mock_sm, mock_claude):
        """2000자 초과 응답은 여러 메시지로 분할된다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        long_text = "A" * 4500
        mock_claude.stream_message = MagicMock(
            return_value=async_stream(
                StreamEvent(event_type="assistant", text=long_text),
                StreamEvent(event_type="result", text="", session_id="s1"),
            )
        )

        ch = make_mock_channel()
        msg = make_mock_message("long", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        # 2000 + 2000 + 500 = 3 messages
        assert len(ch._sent) == 3
        assert len(ch._sent[0].content) == 2000
        assert len(ch._sent[1].content) == 2000
        assert len(ch._sent[2].content) == 500

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_session_id_updated(self, mock_sm, mock_claude):
        """스트림에서 session_id를 추출하여 세션을 갱신한다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        mock_claude.stream_message = MagicMock(
            return_value=async_stream(
                StreamEvent(event_type="system", session_id="new-session-123"),
                StreamEvent(event_type="assistant", text="응답"),
                StreamEvent(event_type="result", text="", session_id="new-session-123"),
            )
        )

        ch = make_mock_channel()
        msg = make_mock_message("테스트", channel=ch)
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

        mock_claude.stream_message = MagicMock(
            return_value=async_stream(
                StreamEvent(event_type="system", session_id="existing-session"),
                StreamEvent(event_type="assistant", text="이어서 응답"),
                StreamEvent(
                    event_type="result", text="", session_id="existing-session"
                ),
            )
        )

        ch = make_mock_channel()
        msg = make_mock_message("이어서", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        mock_claude.stream_message.assert_called_once_with(
            "이어서", session_id="existing-session"
        )

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_no_text_does_not_save_assistant(self, mock_sm, mock_claude):
        """응답 텍스트가 없으면 assistant 메시지를 저장하지 않는다"""
        session = MagicMock()
        session.session_id = None
        mock_sm.get_or_create_session.return_value = session

        mock_claude.stream_message = MagicMock(
            return_value=async_stream(
                StreamEvent(event_type="error", text="CLI 오류"),
            )
        )

        ch = make_mock_channel()
        msg = make_mock_message("테스트", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        session.add_message.assert_called_once_with("user", "테스트")
