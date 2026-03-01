"""Bot-console 채널 생성 및 권한 관리 모듈"""

from typing import Optional

import discord


BOT_CONSOLE_CATEGORY = "🤖 Bot Consoles"
BOT_CONSOLE_PREFIX = "bot-console-"


class ChannelManager:
    """Bot-console 채널 관리"""

    def __init__(self, guild: discord.Guild):
        self.guild = guild

    async def get_or_create_category(self) -> discord.CategoryChannel:
        """Bot-console 카테고리 조회/생성"""
        category = discord.utils.get(
            self.guild.categories, name=BOT_CONSOLE_CATEGORY
        )
        if not category:
            category = await self.guild.create_category(BOT_CONSOLE_CATEGORY)
        return category

    async def create_user_console(
        self, member: discord.Member
    ) -> discord.TextChannel:
        """유저별 bot-console 채널 생성

        이미 존재하면 기존 채널을 반환한다.
        """
        if member.bot:
            raise ValueError("봇에게는 콘솔 채널을 생성할 수 없습니다")

        category = await self.get_or_create_category()
        channel_name = f"{BOT_CONSOLE_PREFIX}{member.name}"

        # 기존 채널 확인
        existing = discord.utils.get(category.channels, name=channel_name)
        if existing:
            return existing

        # 권한 설정
        overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(
                read_messages=False,
                send_messages=False,
            ),
            member: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ),
            self.guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
            ),
        }

        channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"{member.name}님의 AI 대화 채널",
        )
        return channel

    async def get_user_console(
        self, member: discord.Member
    ) -> Optional[discord.TextChannel]:
        """유저의 bot-console 채널 조회"""
        category = await self.get_or_create_category()
        channel_name = f"{BOT_CONSOLE_PREFIX}{member.name}"
        return discord.utils.get(category.channels, name=channel_name)

    @staticmethod
    def is_console_channel(channel: discord.TextChannel) -> bool:
        """해당 채널이 bot-console인지 확인"""
        return channel.name.startswith(BOT_CONSOLE_PREFIX)
