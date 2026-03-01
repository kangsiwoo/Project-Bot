"""Discord 메시지 스트리밍 업데이트 모듈

Claude Code의 스트리밍 이벤트를 Discord 메시지로 실시간 전송/수정한다.
"""

import asyncio
import time
from typing import Optional

import discord

from claude_code_client import StreamEvent

DISCORD_MSG_LIMIT = 2000
MIN_EDIT_INTERVAL = 1.0  # Discord API rate limit 대응 (초)


class DiscordStreamHandler:
    """스트리밍 이벤트를 Discord 메시지로 실시간 업데이트한다."""

    def __init__(self, channel: discord.TextChannel):
        self.channel = channel
        self._current_message: Optional[discord.Message] = None
        self._buffer: str = ""
        self._last_edit_time: float = 0
        self._messages_sent: list[discord.Message] = []

    async def handle_event(self, event: StreamEvent) -> None:
        """스트리밍 이벤트를 처리하여 Discord 메시지를 생성/수정한다."""
        if event.event_type == "assistant":
            await self._handle_text(event.text)
        elif event.event_type == "result":
            await self._flush()
        elif event.event_type == "error":
            await self.channel.send(f"⚠️ {event.text}")

    async def _handle_text(self, text: str) -> None:
        """텍스트를 버퍼에 추가하고 Discord 메시지를 업데이트한다."""
        if not text:
            return

        self._buffer += text

        # 2000자 초과 시 현재 메시지를 확정하고 새 메시지 시작
        while len(self._buffer) > DISCORD_MSG_LIMIT:
            chunk = self._buffer[:DISCORD_MSG_LIMIT]
            self._buffer = self._buffer[DISCORD_MSG_LIMIT:]

            if self._current_message:
                await self._current_message.edit(content=chunk)
                self._messages_sent.append(self._current_message)
            else:
                msg = await self.channel.send(chunk)
                self._messages_sent.append(msg)

            self._current_message = None

        # rate limit을 고려하여 업데이트
        now = time.monotonic()
        if now - self._last_edit_time < MIN_EDIT_INTERVAL:
            return

        if self._current_message is None:
            self._current_message = await self.channel.send(self._buffer)
        else:
            await self._current_message.edit(content=self._buffer)

        self._last_edit_time = now

    async def _flush(self) -> None:
        """남은 버퍼를 Discord 메시지에 최종 반영한다."""
        if not self._buffer:
            return

        if self._current_message is None:
            self._current_message = await self.channel.send(self._buffer)
        else:
            await self._current_message.edit(content=self._buffer)

        self._messages_sent.append(self._current_message)
        self._current_message = None
        self._buffer = ""

    def get_full_text(self) -> str:
        """전송된 전체 텍스트를 반환한다."""
        parts = []
        for msg in self._messages_sent:
            if hasattr(msg, "content"):
                parts.append(msg.content)
        return "".join(parts)
