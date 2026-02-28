"""Project Bot MCP 도구 단위 테스트"""

import asyncio
import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import os
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

import discord
from server import (
    handle_create_project,
    handle_add_team,
    handle_add_channel,
    handle_delete_project,
    handle_list_projects,
    handle_send_notification,
    handle_send_message,
    handle_read_messages,
    find_channel,
)


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def make_mock_guild(categories_spec=None):
    """모킹된 Guild를 생성한다.

    categories_spec: {카테고리명: [채널명, ...]} 또는 None
    """
    guild = MagicMock()
    cats = []

    if categories_spec:
        for cat_name, ch_names in categories_spec.items():
            cat = _make_category(cat_name, ch_names)
            cats.append(cat)

    guild.categories = cats

    async def mock_create_category(name):
        cat = _make_category(name, [])
        cats.append(cat)
        return cat

    guild.create_category = mock_create_category
    return guild


def _make_category(name, ch_names):
    cat = MagicMock()
    cat.name = name
    channels = []
    for ch_name in ch_names:
        ch = MagicMock()
        ch.name = ch_name
        ch.send = AsyncMock()
        ch.delete = AsyncMock()
        channels.append(ch)
    cat.channels = channels
    cat.create_text_channel = AsyncMock()
    cat.delete = AsyncMock()
    return cat


def make_mock_message(author_name, content, time_str="2026-02-28 14:30"):
    msg = MagicMock()
    msg.author.display_name = author_name
    msg.content = content
    msg.created_at = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    return msg


# ---------------------------------------------------------------------------
# create_project
# ---------------------------------------------------------------------------

class TestCreateProject:
    def test_default_teams(self):
        guild = make_mock_guild()
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_create_project({"project_name": "my-app"}))
        text = result[0].text
        assert "카테고리 5개" in text
        assert "채널 15개" in text
        assert len(guild.categories) == 5

    def test_custom_teams(self):
        guild = make_mock_guild()
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(
                handle_create_project({"project_name": "my-app", "teams": "QA, 디자인"})
            )
        text = result[0].text
        assert "카테고리 2개" in text
        assert "채널 4개" in text

    def test_single_custom_team(self):
        guild = make_mock_guild()
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(
                handle_create_project({"project_name": "p", "teams": "AI"})
            )
        assert "카테고리 1개" in result[0].text
        assert "채널 2개" in result[0].text


# ---------------------------------------------------------------------------
# add_team
# ---------------------------------------------------------------------------

class TestAddTeam:
    def test_add_custom_team(self):
        guild = make_mock_guild({"my-app / 기획": [], "my-app / 공통": []})
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(
                handle_add_team({"project_name": "my-app", "team_name": "QA"})
            )
        assert "QA" in result[0].text
        assert "채널 2개" in result[0].text

    def test_add_default_template_team(self):
        guild = make_mock_guild({"my-app / 공통": []})
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(
                handle_add_team({"project_name": "my-app", "team_name": "기획"})
            )
        assert "채널 3개" in result[0].text

    def test_project_not_found(self):
        guild = make_mock_guild()
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_add_team({"project_name": "x", "team_name": "QA"}))
                assert False
            except ValueError as e:
                assert "찾을 수 없습니다" in str(e)

    def test_duplicate_team(self):
        guild = make_mock_guild({"my-app / QA": []})
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_add_team({"project_name": "my-app", "team_name": "QA"}))
                assert False
            except ValueError as e:
                assert "이미 존재합니다" in str(e)


# ---------------------------------------------------------------------------
# add_channel
# ---------------------------------------------------------------------------

class TestAddChannel:
    def test_success(self):
        guild = make_mock_guild({"my-app / 기획": ["📋-기획-일반"]})
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_add_channel({
                "project_name": "my-app",
                "team_name": "기획",
                "channel_name": "📝-새채널",
            }))
        assert "생성 완료" in result[0].text
        guild.categories[0].create_text_channel.assert_called_once_with("📝-새채널")

    def test_category_not_found(self):
        guild = make_mock_guild({"my-app / 기획": []})
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_add_channel({
                    "project_name": "my-app", "team_name": "없는팀", "channel_name": "x",
                }))
                assert False
            except ValueError as e:
                assert "찾을 수 없습니다" in str(e)

    def test_duplicate_channel(self):
        guild = make_mock_guild({"my-app / 기획": ["📋-기획-일반"]})
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_add_channel({
                    "project_name": "my-app", "team_name": "기획", "channel_name": "📋-기획-일반",
                }))
                assert False
            except ValueError as e:
                assert "이미 존재합니다" in str(e)


# ---------------------------------------------------------------------------
# delete_project
# ---------------------------------------------------------------------------

class TestDeleteProject:
    def test_delete_success(self):
        guild = make_mock_guild({
            "my-app / 기획": ["📋-기획-일반", "📝-회의록"],
            "my-app / 공통": ["🤖-claude-알림"],
            "other / 공통": ["💬-자유톡"],
        })
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_delete_project({"project_name": "my-app"}))
        text = result[0].text
        assert "카테고리 2개" in text
        assert "채널 3개" in text
        # other 프로젝트는 삭제되지 않음
        guild.categories[2].delete.assert_not_called()

    def test_project_not_found(self):
        guild = make_mock_guild()
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_delete_project({"project_name": "없는프로젝트"}))
                assert False
            except ValueError as e:
                assert "찾을 수 없습니다" in str(e)


# ---------------------------------------------------------------------------
# list_projects
# ---------------------------------------------------------------------------

class TestListProjects:
    def test_multiple_projects(self):
        guild = make_mock_guild({
            "my-app / 기획": [],
            "my-app / 백엔드": [],
            "other / 공통": [],
            "일반카테고리": [],
        })
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_list_projects({}))
        data = json.loads(result[0].text)
        assert "my-app" in data
        assert len(data["my-app"]) == 2
        assert "other" in data
        assert "일반카테고리" not in data

    def test_empty(self):
        guild = make_mock_guild()
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_list_projects({}))
        assert "등록된 프로젝트가 없습니다" in result[0].text


# ---------------------------------------------------------------------------
# send_notification
# ---------------------------------------------------------------------------

class TestSendNotification:
    def _make_guild_with_alert(self):
        alert_ch = MagicMock()
        alert_ch.name = "🤖-claude-알림"
        alert_ch.send = AsyncMock()
        guild = make_mock_guild({"my-app / 공통": []})
        guild.categories[0].channels = [alert_ch]
        return guild, alert_ch

    def test_plan(self):
        guild, alert_ch = self._make_guild_with_alert()
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_send_notification({
                "project_name": "my-app", "message": "계획 수립", "event_type": "plan",
            }))
        assert "플랜 작성" in result[0].text
        embed = alert_ch.send.call_args.kwargs.get("embed") or alert_ch.send.call_args.args[0]
        assert isinstance(embed, discord.Embed)
        assert embed.color.value == 0x3498DB

    def test_error(self):
        guild, alert_ch = self._make_guild_with_alert()
        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_send_notification({
                "project_name": "my-app", "message": "빌드 실패", "event_type": "error",
            }))
        embed = alert_ch.send.call_args.kwargs.get("embed") or alert_ch.send.call_args.args[0]
        assert embed.color.value == 0xE74C3C

    def test_channel_not_found(self):
        guild = make_mock_guild({"my-app / 기획": ["📋-기획-일반"]})
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_send_notification({
                    "project_name": "my-app", "message": "t", "event_type": "plan",
                }))
                assert False
            except ValueError as e:
                assert "claude-알림" in str(e)

    def test_invalid_event_type(self):
        guild = make_mock_guild()
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_send_notification({
                    "project_name": "my-app", "message": "t", "event_type": "invalid",
                }))
                assert False
            except ValueError as e:
                assert "알 수 없는 event_type" in str(e)


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

class TestSendMessage:
    def test_success(self):
        ch = MagicMock()
        ch.name = "💬-자유톡"
        ch.send = AsyncMock()
        guild = make_mock_guild({"my-app / 공통": []})
        guild.categories[0].channels = [ch]

        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_send_message({
                "project_name": "my-app", "channel_keyword": "자유톡", "content": "hello",
            }))
        assert "전송 완료" in result[0].text
        ch.send.assert_called_once_with("hello")

    def test_channel_not_found(self):
        guild = make_mock_guild({"my-app / 공통": ["💬-자유톡"]})
        with patch("server.get_guild", return_value=guild):
            try:
                asyncio.run(handle_send_message({
                    "project_name": "my-app", "channel_keyword": "없는채널", "content": "t",
                }))
                assert False
            except ValueError as e:
                assert "찾을 수 없습니다" in str(e)


# ---------------------------------------------------------------------------
# read_messages
# ---------------------------------------------------------------------------

class TestReadMessages:
    def test_success(self):
        msg1 = make_mock_message("Alice", "첫 번째", "2026-02-28 14:00")
        msg2 = make_mock_message("Bob", "두 번째", "2026-02-28 14:05")

        ch = MagicMock()
        ch.name = "💬-자유톡"

        async def mock_history(limit=10):
            for m in [msg1, msg2]:
                yield m

        ch.history = mock_history

        guild = make_mock_guild({"my-app / 공통": []})
        guild.categories[0].channels = [ch]

        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_read_messages({
                "project_name": "my-app", "channel_keyword": "자유톡", "limit": 10,
            }))
        text = result[0].text
        assert "Alice" in text
        assert "Bob" in text

    def test_empty(self):
        ch = MagicMock()
        ch.name = "💬-자유톡"

        async def mock_history(limit=10):
            return
            yield

        ch.history = mock_history

        guild = make_mock_guild({"my-app / 공통": []})
        guild.categories[0].channels = [ch]

        with patch("server.get_guild", return_value=guild):
            result = asyncio.run(handle_read_messages({
                "project_name": "my-app", "channel_keyword": "자유톡",
            }))
        assert "메시지가 없습니다" in result[0].text


# ---------------------------------------------------------------------------
# find_channel 헬퍼
# ---------------------------------------------------------------------------

class TestFindChannel:
    def test_found(self):
        guild = make_mock_guild({"my-app / 공통": ["💬-자유톡", "📢-공지사항"]})
        ch = find_channel(guild, "my-app", "자유톡")
        assert ch is not None
        assert ch.name == "💬-자유톡"

    def test_not_found(self):
        guild = make_mock_guild({"my-app / 공통": ["💬-자유톡"]})
        ch = find_channel(guild, "my-app", "없는채널")
        assert ch is None

    def test_wrong_project(self):
        guild = make_mock_guild({"other / 공통": ["💬-자유톡"]})
        ch = find_channel(guild, "my-app", "자유톡")
        assert ch is None
