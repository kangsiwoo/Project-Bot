"""on_ready 이벤트 핸들러 단위 테스트"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# server.py 임포트 전에 환경변수 설정
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

import discord


def make_mock_member(name, is_bot=False):
    member = MagicMock()
    member.name = name
    member.bot = is_bot
    member.mention = f"<@{name}>"
    return member


def make_mock_channel(has_messages=False):
    ch = MagicMock()
    ch.last_message_id = 12345 if has_messages else None
    ch.send = AsyncMock()
    return ch


class TestOnReady:
    def _run(self, coro):
        return asyncio.run(coro)

    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_creates_channels_for_non_bot_members(self, mock_bot, MockChannelMgr):
        """봇이 아닌 멤버에게만 채널을 생성한다"""
        guild = MagicMock()
        members = [
            make_mock_member("alice"),
            make_mock_member("bot-user", is_bot=True),
            make_mock_member("bob"),
        ]
        guild.members = members
        mock_bot.get_guild.return_value = guild

        new_ch = make_mock_channel(has_messages=False)
        mgr_instance = MockChannelMgr.return_value
        mgr_instance.create_user_console = AsyncMock(return_value=new_ch)

        from server import on_ready

        self._run(on_ready())

        assert mgr_instance.create_user_console.call_count == 2
        calls = mgr_instance.create_user_console.call_args_list
        called_members = [c.args[0] for c in calls]
        assert members[0] in called_members
        assert members[2] in called_members

    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_sends_welcome_to_new_channels(self, mock_bot, MockChannelMgr):
        """새로 생성된 채널(메시지 없음)에 웰컴 메시지를 전송한다"""
        guild = MagicMock()
        guild.members = [make_mock_member("alice")]
        mock_bot.get_guild.return_value = guild

        new_ch = make_mock_channel(has_messages=False)
        mgr_instance = MockChannelMgr.return_value
        mgr_instance.create_user_console = AsyncMock(return_value=new_ch)

        from server import on_ready

        self._run(on_ready())

        new_ch.send.assert_called_once()
        msg = new_ch.send.call_args.args[0]
        assert "<@alice>" in msg

    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_skips_welcome_for_existing_channels(self, mock_bot, MockChannelMgr):
        """이미 메시지가 있는 채널에는 웰컴 메시지를 보내지 않는다"""
        guild = MagicMock()
        guild.members = [make_mock_member("alice")]
        mock_bot.get_guild.return_value = guild

        existing_ch = make_mock_channel(has_messages=True)
        mgr_instance = MockChannelMgr.return_value
        mgr_instance.create_user_console = AsyncMock(return_value=existing_ch)

        from server import on_ready

        self._run(on_ready())

        existing_ch.send.assert_not_called()

    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_guild_not_found(self, mock_bot, MockChannelMgr):
        """guild를 찾을 수 없으면 아무 작업도 하지 않는다"""
        mock_bot.get_guild.return_value = None

        from server import on_ready

        self._run(on_ready())

        MockChannelMgr.assert_not_called()

    @patch("server.ChannelManager")
    @patch("server.bot")
    def test_continues_on_member_error(self, mock_bot, MockChannelMgr):
        """한 멤버에서 에러가 발생해도 나머지 멤버는 계속 처리한다"""
        guild = MagicMock()
        guild.members = [
            make_mock_member("alice"),
            make_mock_member("bob"),
        ]
        mock_bot.get_guild.return_value = guild

        new_ch = make_mock_channel(has_messages=False)
        mgr_instance = MockChannelMgr.return_value
        mgr_instance.create_user_console = AsyncMock(
            side_effect=[Exception("테스트 에러"), new_ch]
        )

        from server import on_ready

        self._run(on_ready())

        assert mgr_instance.create_user_console.call_count == 2
        new_ch.send.assert_called_once()
