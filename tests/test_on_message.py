"""on_message 이벤트 핸들러 단위 테스트"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

from claude_code_client import ClaudeResponse


def make_mock_channel(name="bot-console-alice", channel_id=900):
    """typing() async context manager를 포함한 mock 채널을 생성한다."""
    ch = MagicMock()
    ch.name = name
    ch.id = channel_id
    sent_messages = []

    async def mock_send(content):
        msg = MagicMock()
        msg.content = content
        sent_messages.append(msg)
        return msg

    ch.send = AsyncMock(side_effect=mock_send)

    typing_cm = MagicMock()
    typing_cm.__aenter__ = AsyncMock(return_value=None)
    typing_cm.__aexit__ = AsyncMock(return_value=None)
    ch.typing = MagicMock(return_value=typing_cm)

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
        """bot-console 채널에서 AI 응답을 전송한다"""
        session = MagicMock()
        session.get_recent_messages.return_value = []
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(text="안녕하세요!", success=True)
        )

        ch = make_mock_channel()
        msg = make_mock_message("안녕", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        mock_claude.send_message.assert_called_once()
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

        mock_claude.send_message.assert_not_called()
        mock_sm.get_or_create_session.assert_not_called()

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_ignores_non_console_channel(self, mock_sm, mock_claude):
        """bot-console이 아닌 채널은 무시한다"""
        ch = make_mock_channel(name="general")
        msg = make_mock_message("test", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        mock_claude.send_message.assert_not_called()
        mock_sm.get_or_create_session.assert_not_called()

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_error_response(self, mock_sm, mock_claude):
        """CLI 에러 시 경고 메시지를 전송한다"""
        session = MagicMock()
        session.get_recent_messages.return_value = []
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(text="", success=False, error="타임아웃")
        )

        ch = make_mock_channel()
        msg = make_mock_message("테스트", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        assert ch.send.call_count >= 1
        assert "타임아웃" in ch._sent[0].content

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_context_messages_passed(self, mock_sm, mock_claude):
        """이전 대화 컨텍스트가 send_message에 전달된다"""
        session = MagicMock()
        context = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
        ]
        session.get_recent_messages.return_value = context
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(text="응답", success=True)
        )

        ch = make_mock_channel()
        msg = make_mock_message("새 질문", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        call_args = mock_claude.send_message.call_args
        assert call_args.args[0] == "새 질문"
        assert call_args.kwargs["context_messages"] == context

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_no_assistant_message_on_error(self, mock_sm, mock_claude):
        """에러 시 assistant 메시지를 저장하지 않는다"""
        session = MagicMock()
        session.get_recent_messages.return_value = []
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(text="", success=False, error="오류")
        )

        ch = make_mock_channel()
        msg = make_mock_message("테스트", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        session.add_message.assert_called_once_with("user", "테스트")

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_long_response_split(self, mock_sm, mock_claude):
        """긴 응답이 split_message로 분할되어 전송된다"""
        session = MagicMock()
        session.get_recent_messages.return_value = []
        mock_sm.get_or_create_session.return_value = session

        long_text = "A" * 4500
        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(text=long_text, success=True)
        )

        ch = make_mock_channel()
        msg = make_mock_message("long", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        # 4500자 → 2000 + 2000 + 500 = 3 messages
        assert len(ch._sent) == 3

    @patch("server.claude_client")
    @patch("server.session_manager")
    def test_typing_indicator_shown(self, mock_sm, mock_claude):
        """응답 생성 중 typing indicator가 표시된다"""
        session = MagicMock()
        session.get_recent_messages.return_value = []
        mock_sm.get_or_create_session.return_value = session

        mock_claude.send_message = AsyncMock(
            return_value=ClaudeResponse(text="응답", success=True)
        )

        ch = make_mock_channel()
        msg = make_mock_message("테스트", channel=ch)
        from server import on_message

        self._run(on_message(msg))

        ch.typing.assert_called_once()


class TestSplitMessage:
    def test_short_message(self):
        """2000자 이하는 분할하지 않는다"""
        from server import split_message

        result = split_message("짧은 메시지")
        assert result == ["짧은 메시지"]

    def test_empty_string(self):
        """빈 문자열은 빈 리스트를 반환한다"""
        from server import split_message

        result = split_message("")
        assert result == []

    def test_exact_limit(self):
        """정확히 2000자는 분할하지 않는다"""
        from server import split_message

        text = "A" * 2000
        result = split_message(text)
        assert len(result) == 1

    def test_splits_at_newline(self):
        """긴 메시지는 줄바꿈 기준으로 분할한다"""
        from server import split_message

        text = "A" * 1990 + "\n" + "B" * 100
        result = split_message(text)
        assert len(result) == 2
        assert result[0] == "A" * 1990
        assert result[1] == "B" * 100

    def test_code_block_preserved(self):
        """코드블록이 분할 시 닫히고 다시 열린다"""
        from server import split_message

        # 코드블록 시작 + 긴 내용
        text = "```\n" + "A" * 2010 + "\n```"
        result = split_message(text, limit=2000)
        assert len(result) >= 2
        # 첫 번째 청크는 열린 코드블록을 닫아야 한다
        assert result[0].endswith("```")
        # 두 번째 청크는 코드블록을 다시 열어야 한다
        assert result[1].startswith("```")

    def test_no_code_block_normal_split(self):
        """코드블록 없는 긴 메시지는 정상 분할한다"""
        from server import split_message

        text = "A" * 4500
        result = split_message(text)
        total = sum(len(chunk) for chunk in result)
        assert total == 4500

    def test_splits_at_space_when_no_newline(self):
        """줄바꿈이 없으면 공백 기준으로 분할한다"""
        from server import split_message

        text = ("word " * 500).strip()  # 약 2499자
        result = split_message(text, limit=2000)
        assert len(result) >= 2
        # 각 청크가 limit을 초과하지 않음
        for chunk in result:
            assert len(chunk) <= 2000 + 4  # 코드블록 닫힘 태그 허용
