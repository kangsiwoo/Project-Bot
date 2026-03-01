"""discord_stream_handler 단위 테스트"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from claude_code_client import StreamEvent
from discord_stream_handler import (
    DiscordStreamHandler,
    DISCORD_MSG_LIMIT,
    MIN_EDIT_INTERVAL,
)


def make_mock_channel():
    ch = MagicMock()
    sent_messages = []

    async def mock_send(content):
        msg = MagicMock()
        msg.content = content
        msg.edit = AsyncMock(side_effect=lambda content: setattr(msg, "content", content))
        sent_messages.append(msg)
        return msg

    ch.send = AsyncMock(side_effect=mock_send)
    ch._sent = sent_messages
    return ch


class TestDiscordStreamHandler:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_assistant_event_creates_message(self):
        """첫 텍스트 이벤트가 새 메시지를 생성한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        event = StreamEvent(event_type="assistant", text="안녕하세요!")
        self._run(handler.handle_event(event))

        assert ch.send.call_count == 1
        assert ch._sent[0].content == "안녕하세요!"

    def test_subsequent_text_edits_message(self):
        """이어지는 텍스트가 기존 메시지를 수정한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text="Hello ")
        ))
        # rate limit 회피: 마지막 edit 시간을 과거로 설정
        handler._last_edit_time = 0

        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text="World!")
        ))

        # send 1번, edit 1번
        assert ch.send.call_count == 1
        assert ch._sent[0].content == "Hello World!"

    def test_rate_limit_skips_edit(self):
        """rate limit 이내의 edit는 스킵한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text="first")
        ))
        # _last_edit_time을 방금으로 설정하여 rate limit 발동
        import time
        handler._last_edit_time = time.monotonic()

        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text=" second")
        ))

        # send 1번만, edit은 rate limit으로 스킵
        assert ch.send.call_count == 1
        # 버퍼에는 쌓여있음
        assert handler._buffer == "first second"

    def test_result_event_flushes_buffer(self):
        """result 이벤트가 남은 버퍼를 최종 전송한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)
        handler._buffer = "남은 텍스트"

        self._run(handler.handle_event(
            StreamEvent(event_type="result", text="최종", session_id="s1")
        ))

        assert ch.send.call_count == 1
        assert ch._sent[0].content == "남은 텍스트"
        assert handler._buffer == ""

    def test_result_with_existing_message_edits(self):
        """result 이벤트 시 기존 메시지가 있으면 edit한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        # 먼저 메시지 생성
        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text="진행중...")
        ))

        # 버퍼에 추가 텍스트 쌓임 (rate limit으로 아직 edit 안됨)
        handler._buffer = "진행중... 완료!"

        # result로 flush
        self._run(handler.handle_event(
            StreamEvent(event_type="result", text="", session_id="s1")
        ))

        assert ch._sent[0].content == "진행중... 완료!"

    def test_error_event_sends_warning(self):
        """에러 이벤트가 경고 메시지를 전송한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        self._run(handler.handle_event(
            StreamEvent(event_type="error", text="타임아웃")
        ))

        ch.send.assert_called_once()
        assert "타임아웃" in ch.send.call_args.args[0]

    def test_empty_text_ignored(self):
        """빈 텍스트는 무시한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text="")
        ))

        ch.send.assert_not_called()

    def test_long_text_splits_into_multiple_messages(self):
        """2000자 초과 텍스트가 여러 메시지로 분할된다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        long_text = "A" * 4500
        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text=long_text)
        ))
        self._run(handler.handle_event(
            StreamEvent(event_type="result", text="", session_id="s1")
        ))

        # 2000 + 2000 + 500 = 3 messages
        assert len(ch._sent) == 3
        assert len(ch._sent[0].content) == 2000
        assert len(ch._sent[1].content) == 2000
        assert len(ch._sent[2].content) == 500

    def test_get_full_text(self):
        """전체 텍스트를 반환한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        self._run(handler.handle_event(
            StreamEvent(event_type="assistant", text="Hello World!")
        ))
        self._run(handler.handle_event(
            StreamEvent(event_type="result", text="", session_id="s1")
        ))

        assert handler.get_full_text() == "Hello World!"

    def test_system_event_ignored(self):
        """system 이벤트는 무시한다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        self._run(handler.handle_event(
            StreamEvent(event_type="system", session_id="s1")
        ))

        ch.send.assert_not_called()

    def test_empty_result_no_flush(self):
        """버퍼가 비어있을 때 result는 아무 동작도 하지 않는다"""
        ch = make_mock_channel()
        handler = DiscordStreamHandler(ch)

        self._run(handler.handle_event(
            StreamEvent(event_type="result", text="", session_id="s1")
        ))

        ch.send.assert_not_called()
