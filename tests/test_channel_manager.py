"""channel_manager 단위 테스트"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import discord

from channel_manager import BOT_CONSOLE_CATEGORY, BOT_CONSOLE_PREFIX, ChannelManager


def make_mock_guild(categories=None):
    guild = MagicMock()
    guild.categories = categories or []
    guild.create_category = AsyncMock()
    guild.me = MagicMock()
    guild.default_role = MagicMock()
    return guild


def make_mock_member(name, is_bot=False):
    member = MagicMock()
    member.name = name
    member.bot = is_bot
    return member


def make_mock_category(name, channels=None):
    cat = MagicMock()
    cat.name = name
    cat.channels = channels or []
    cat.create_text_channel = AsyncMock()
    return cat


class TestGetOrCreateCategory:
    def test_create_new(self):
        guild = make_mock_guild()
        new_cat = make_mock_category(BOT_CONSOLE_CATEGORY)
        guild.create_category = AsyncMock(return_value=new_cat)

        mgr = ChannelManager(guild)
        result = asyncio.run(mgr.get_or_create_category())

        guild.create_category.assert_called_once_with(BOT_CONSOLE_CATEGORY)
        assert result == new_cat

    def test_return_existing(self):
        existing_cat = make_mock_category(BOT_CONSOLE_CATEGORY)
        guild = make_mock_guild(categories=[existing_cat])

        mgr = ChannelManager(guild)
        result = asyncio.run(mgr.get_or_create_category())

        guild.create_category.assert_not_called()
        assert result == existing_cat


class TestCreateUserConsole:
    def test_create_new_channel(self):
        cat = make_mock_category(BOT_CONSOLE_CATEGORY)
        new_ch = MagicMock()
        cat.create_text_channel = AsyncMock(return_value=new_ch)
        guild = make_mock_guild(categories=[cat])
        member = make_mock_member("alice")

        mgr = ChannelManager(guild)
        result = asyncio.run(mgr.create_user_console(member))

        cat.create_text_channel.assert_called_once()
        call_args = cat.create_text_channel.call_args
        channel_name = call_args.args[0] if call_args.args else call_args.kwargs.get("name")
        assert channel_name == "bot-console-alice"
        assert result == new_ch

    def test_return_existing_channel(self):
        existing_ch = MagicMock()
        existing_ch.name = "bot-console-alice"
        cat = make_mock_category(BOT_CONSOLE_CATEGORY, channels=[existing_ch])
        guild = make_mock_guild(categories=[cat])
        member = make_mock_member("alice")

        mgr = ChannelManager(guild)
        result = asyncio.run(mgr.create_user_console(member))

        cat.create_text_channel.assert_not_called()
        assert result == existing_ch

    def test_reject_bot_member(self):
        guild = make_mock_guild()
        bot_member = make_mock_member("bot-user", is_bot=True)

        mgr = ChannelManager(guild)
        try:
            asyncio.run(mgr.create_user_console(bot_member))
            assert False, "ValueError가 발생해야 합니다"
        except ValueError as e:
            assert "봇" in str(e)

    def test_permission_overwrites(self):
        cat = make_mock_category(BOT_CONSOLE_CATEGORY)
        guild = make_mock_guild(categories=[cat])
        member = make_mock_member("alice")

        mgr = ChannelManager(guild)
        asyncio.run(mgr.create_user_console(member))

        call_kwargs = cat.create_text_channel.call_args.kwargs
        overwrites = call_kwargs["overwrites"]

        # default_role은 읽기 차단
        assert overwrites[guild.default_role].read_messages is False
        # 유저는 읽기/쓰기 허용
        assert overwrites[member].read_messages is True
        assert overwrites[member].send_messages is True
        # 봇은 관리 권한 포함
        assert overwrites[guild.me].manage_messages is True


class TestGetUserConsole:
    def test_found(self):
        ch = MagicMock()
        ch.name = "bot-console-alice"
        cat = make_mock_category(BOT_CONSOLE_CATEGORY, channels=[ch])
        guild = make_mock_guild(categories=[cat])
        member = make_mock_member("alice")

        mgr = ChannelManager(guild)
        result = asyncio.run(mgr.get_user_console(member))
        assert result == ch

    def test_not_found(self):
        cat = make_mock_category(BOT_CONSOLE_CATEGORY)
        guild = make_mock_guild(categories=[cat])
        member = make_mock_member("bob")

        mgr = ChannelManager(guild)
        result = asyncio.run(mgr.get_user_console(member))
        assert result is None


class TestIsConsoleChannel:
    def test_true(self):
        ch = MagicMock()
        ch.name = "bot-console-alice"
        assert ChannelManager.is_console_channel(ch) is True

    def test_false(self):
        ch = MagicMock()
        ch.name = "💬-자유톡"
        assert ChannelManager.is_console_channel(ch) is False
