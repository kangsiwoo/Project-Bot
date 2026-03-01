"""Bot-Console 통합 테스트

on_ready → 채널 생성 → on_message → Claude Code 스트리밍 응답의 전체 흐름을 검증한다.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

from claude_code_client import StreamEvent
from session_manager import SessionManager


async def async_stream(*events):
    """StreamEvent 리스트를 async generator로 변환한다."""
    for event in events:
        yield event


def make_mock_member(name, member_id, is_bot=False):
    member = MagicMock()
    member.name = name
    member.id = member_id
    member.bot = is_bot
    member.mention = f"<@{member_id}>"
    return member


def make_mock_channel(name, has_messages=False):
    ch = MagicMock()
    ch.name = name
    ch.last_message_id = 12345 if has_messages else None
    sent_messages = []

    async def mock_send(content=None, **kwargs):
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


def make_mock_message(content, author, channel):
    msg = MagicMock()
    msg.content = content
    msg.author = author
    msg.channel = channel
    return msg


class TestFullFlow:
    """on_ready → on_message → AI 스트리밍 응답 전체 흐름 통합 테스트"""

    def _run(self, coro):
        return asyncio.run(coro)

    @patch("server.claude_client")
    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_ready_then_message_flow(self, mock_bot, MockChannelMgr, mock_claude):
        """on_ready로 채널 생성 후 on_message 스트리밍으로 AI 대화가 동작한다"""
        real_sm = SessionManager()

        with patch("server.session_manager", real_sm):
            alice = make_mock_member("alice", 111)
            bot_user = make_mock_member("bot-user", 222, is_bot=True)

            guild = MagicMock()
            guild.members = [alice, bot_user]
            mock_bot.get_guild.return_value = guild

            # on_ready: 채널 생성
            new_ch = make_mock_channel("bot-console-alice", has_messages=False)
            mgr_instance = MockChannelMgr.return_value
            mgr_instance.create_user_console = AsyncMock(return_value=new_ch)

            from server import on_ready

            self._run(on_ready())

            # 채널이 alice에게만 생성됨 (봇은 스킵)
            assert mgr_instance.create_user_console.call_count == 1
            mgr_instance.create_user_console.assert_called_with(alice)
            assert new_ch.send.call_count == 1  # 웰컴 메시지

            # on_message: 스트리밍 AI 응답
            mock_claude.stream_message = MagicMock(
                return_value=async_stream(
                    StreamEvent(event_type="system", session_id="sess-1"),
                    StreamEvent(event_type="assistant", text="프로젝트를 생성했습니다!"),
                    StreamEvent(event_type="result", text="", session_id="sess-1"),
                )
            )

            console_ch = make_mock_channel("bot-console-alice")
            msg = make_mock_message("프로젝트 만들어줘", alice, console_ch)

            from server import on_message

            self._run(on_message(msg))

            mock_claude.stream_message.assert_called_once_with(
                "프로젝트 만들어줘", session_id=None
            )

            # 세션에 대화 기록이 저장됨
            session = real_sm.get_or_create_session("111")
            msgs = session.get_messages()
            assert len(msgs) == 2
            assert msgs[0] == {"role": "user", "content": "프로젝트 만들어줘"}
            assert msgs[1] == {
                "role": "assistant",
                "content": "프로젝트를 생성했습니다!",
            }
            assert session.session_id == "sess-1"

    @patch("server.claude_client")
    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_multi_turn_conversation(self, mock_bot, MockChannelMgr, mock_claude):
        """여러 턴의 대화에서 세션이 유지된다"""
        real_sm = SessionManager()

        with patch("server.session_manager", real_sm):
            alice = make_mock_member("alice", 111)

            # 1턴
            mock_claude.stream_message = MagicMock(
                return_value=async_stream(
                    StreamEvent(event_type="system", session_id="sess-1"),
                    StreamEvent(event_type="assistant", text="어떤 프로젝트를 만들까요?"),
                    StreamEvent(event_type="result", text="", session_id="sess-1"),
                )
            )

            ch1 = make_mock_channel("bot-console-alice")
            msg1 = make_mock_message("프로젝트 만들어줘", alice, ch1)
            from server import on_message

            self._run(on_message(msg1))

            # 2턴: session_id 유지 확인
            mock_claude.stream_message = MagicMock(
                return_value=async_stream(
                    StreamEvent(event_type="system", session_id="sess-1"),
                    StreamEvent(
                        event_type="assistant", text="MyApp 프로젝트를 생성했습니다!"
                    ),
                    StreamEvent(event_type="result", text="", session_id="sess-1"),
                )
            )

            ch2 = make_mock_channel("bot-console-alice")
            msg2 = make_mock_message("MyApp으로 해줘", alice, ch2)
            self._run(on_message(msg2))

            mock_claude.stream_message.assert_called_once_with(
                "MyApp으로 해줘", session_id="sess-1"
            )

            session = real_sm.get_or_create_session("111")
            assert len(session.get_messages()) == 4

    @patch("server.claude_client")
    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_multiple_users_isolated(self, mock_bot, MockChannelMgr, mock_claude):
        """서로 다른 유저의 세션이 격리된다"""
        real_sm = SessionManager()

        with patch("server.session_manager", real_sm):
            alice = make_mock_member("alice", 111)
            bob = make_mock_member("bob", 222)

            from server import on_message

            # alice 메시지
            mock_claude.stream_message = MagicMock(
                return_value=async_stream(
                    StreamEvent(event_type="system", session_id="s1"),
                    StreamEvent(event_type="assistant", text="alice 응답"),
                    StreamEvent(event_type="result", text="", session_id="s1"),
                )
            )
            ch_alice = make_mock_channel("bot-console-alice")
            self._run(
                on_message(make_mock_message("alice msg", alice, ch_alice))
            )

            # bob 메시지
            mock_claude.stream_message = MagicMock(
                return_value=async_stream(
                    StreamEvent(event_type="system", session_id="s2"),
                    StreamEvent(event_type="assistant", text="bob 응답"),
                    StreamEvent(event_type="result", text="", session_id="s2"),
                )
            )
            ch_bob = make_mock_channel("bot-console-bob")
            self._run(
                on_message(make_mock_message("bob msg", bob, ch_bob))
            )

            alice_session = real_sm.get_or_create_session("111")
            bob_session = real_sm.get_or_create_session("222")

            assert alice_session.session_id == "s1"
            assert bob_session.session_id == "s2"
            assert len(alice_session.get_messages()) == 2
            assert len(bob_session.get_messages()) == 2

    @patch("server.claude_client")
    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_error_does_not_save_assistant_message(
        self, mock_bot, MockChannelMgr, mock_claude
    ):
        """AI 에러 시 assistant 메시지가 세션에 저장되지 않는다"""
        real_sm = SessionManager()

        with patch("server.session_manager", real_sm):
            alice = make_mock_member("alice", 111)
            console_ch = make_mock_channel("bot-console-alice")

            mock_claude.stream_message = MagicMock(
                return_value=async_stream(
                    StreamEvent(event_type="error", text="타임아웃"),
                )
            )

            msg = make_mock_message("테스트", alice, console_ch)
            from server import on_message

            self._run(on_message(msg))

            session = real_sm.get_or_create_session("111")
            msgs = session.get_messages()
            assert len(msgs) == 1
            assert msgs[0]["role"] == "user"

            assert console_ch.send.call_count >= 1
            assert "타임아웃" in console_ch._sent[0].content

    @patch("server.claude_client")
    @patch("server.bot")
    def test_non_console_channel_ignored_after_ready(
        self, mock_bot, mock_claude
    ):
        """on_ready 후에도 일반 채널 메시지는 무시된다"""
        real_sm = SessionManager()

        with patch("server.session_manager", real_sm):
            alice = make_mock_member("alice", 111)

            from server import on_message

            general_ch = make_mock_channel("general")
            msg = make_mock_message("hello", alice, general_ch)
            self._run(on_message(msg))

            mock_claude.stream_message.assert_not_called()
