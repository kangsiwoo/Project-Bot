import asyncio
import datetime
import json
import os
from typing import Any

import discord
import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from config import DEFAULT_TEAMS, CUSTOM_TEAM_CHANNELS, NOTIFICATION_TYPES

# 환경변수
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')

if not DISCORD_TOKEN or not DISCORD_GUILD_ID:
    raise SystemExit("DISCORD_TOKEN과 DISCORD_GUILD_ID 환경 변수를 설정해주세요.")

DISCORD_GUILD_ID = int(DISCORD_GUILD_ID)

# Discord 봇
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = discord.Client(intents=intents)

# MCP 서버
server = Server("project-bot")


def get_guild() -> discord.Guild:
    """Discord 서버(길드) 객체를 반환한다."""
    guild = bot.get_guild(DISCORD_GUILD_ID)
    if not guild:
        raise ValueError(f"Guild ID {DISCORD_GUILD_ID}를 찾을 수 없습니다")
    return guild


def find_channel(guild: discord.Guild, project_name: str, keyword: str):
    """프로젝트 카테고리 내에서 keyword를 포함하는 채널을 찾는다."""
    prefix = f"{project_name} / "
    for category in guild.categories:
        if not category.name.startswith(prefix):
            continue
        for channel in category.channels:
            if keyword in channel.name:
                return channel
    return None


# ---------------------------------------------------------------------------
# 도구 스키마 등록
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="create_project",
            description="프로젝트 카테고리와 채널을 일괄 생성합니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "프로젝트명"},
                    "teams": {
                        "type": "string",
                        "description": "커스텀 팀명 (쉼표 구분, 선택)",
                    },
                },
                "required": ["project_name"],
            },
        ),
        types.Tool(
            name="add_team",
            description="기존 프로젝트에 새로운 팀 카테고리를 추가합니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "프로젝트명"},
                    "team_name": {"type": "string", "description": "추가할 팀명"},
                },
                "required": ["project_name", "team_name"],
            },
        ),
        types.Tool(
            name="add_channel",
            description="특정 팀에 채널을 추가합니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "프로젝트명"},
                    "team_name": {"type": "string", "description": "팀명"},
                    "channel_name": {
                        "type": "string",
                        "description": "생성할 채널명",
                    },
                },
                "required": ["project_name", "team_name", "channel_name"],
            },
        ),
        types.Tool(
            name="delete_project",
            description="프로젝트의 모든 카테고리와 채널을 삭제합니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "삭제할 프로젝트명"},
                },
                "required": ["project_name"],
            },
        ),
        types.Tool(
            name="list_projects",
            description="등록된 모든 프로젝트 목록을 조회합니다",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="send_notification",
            description="프로젝트의 claude-알림 채널에 Embed 형식 알림을 전송합니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "프로젝트명"},
                    "message": {"type": "string", "description": "알림 메시지"},
                    "event_type": {
                        "type": "string",
                        "description": "알림 타입 (plan/question/complete/error/build/test/deploy)",
                        "enum": list(NOTIFICATION_TYPES.keys()),
                    },
                },
                "required": ["project_name", "message", "event_type"],
            },
        ),
        types.Tool(
            name="send_message",
            description="특정 채널에 일반 메시지를 전송합니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "프로젝트명"},
                    "channel_keyword": {
                        "type": "string",
                        "description": "채널 검색 키워드",
                    },
                    "content": {"type": "string", "description": "메시지 내용"},
                },
                "required": ["project_name", "channel_keyword", "content"],
            },
        ),
        types.Tool(
            name="read_messages",
            description="특정 채널의 최근 메시지를 읽어옵니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "프로젝트명"},
                    "channel_keyword": {
                        "type": "string",
                        "description": "채널 검색 키워드",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "조회할 메시지 수 (기본값 10)",
                        "default": 10,
                    },
                },
                "required": ["project_name", "channel_keyword"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# 도구 핸들러 (Phase 2에서 개별 구현 예정)
# ---------------------------------------------------------------------------

async def handle_create_project(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    project_name = arguments["project_name"]

    # 커스텀 팀이 지정되었으면 파싱, 아니면 기본 템플릿 사용
    custom_teams_raw = arguments.get("teams", "")
    if custom_teams_raw:
        team_names = [t.strip() for t in custom_teams_raw.split(",") if t.strip()]
    else:
        team_names = None

    created_categories = []
    created_channels = []

    if team_names is None:
        # 기본 5개 팀 템플릿
        teams = DEFAULT_TEAMS
    else:
        # 커스텀 팀: CUSTOM_TEAM_CHANNELS 템플릿 사용
        teams = {}
        for name in team_names:
            teams[name] = [
                ch.format(team_name=name) for ch in CUSTOM_TEAM_CHANNELS
            ]

    for team_name, channels in teams.items():
        category_name = f"{project_name} / {team_name}"
        category = await guild.create_category(category_name)
        created_categories.append(category_name)

        for ch_name in channels:
            await category.create_text_channel(ch_name)
            created_channels.append(ch_name)

    summary = (
        f"프로젝트 '{project_name}' 생성 완료\n"
        f"카테고리 {len(created_categories)}개, 채널 {len(created_channels)}개 생성됨\n"
        f"카테고리: {', '.join(created_categories)}"
    )
    return [types.TextContent(type="text", text=summary)]


async def handle_add_team(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    project_name = arguments["project_name"]
    team_name = arguments["team_name"]
    prefix = f"{project_name} / "

    # 프로젝트 존재 확인
    project_categories = [c for c in guild.categories if c.name.startswith(prefix)]
    if not project_categories:
        raise ValueError(f"프로젝트 '{project_name}'를 찾을 수 없습니다")

    # 팀 중복 확인
    new_category_name = f"{project_name} / {team_name}"
    if any(c.name == new_category_name for c in guild.categories):
        raise ValueError(f"팀 '{team_name}'이(가) 이미 존재합니다")

    # 기본 템플릿에 있는 팀이면 해당 채널, 아니면 커스텀 채널
    if team_name in DEFAULT_TEAMS:
        channels = DEFAULT_TEAMS[team_name]
    else:
        channels = [ch.format(team_name=team_name) for ch in CUSTOM_TEAM_CHANNELS]

    category = await guild.create_category(new_category_name)
    for ch_name in channels:
        await category.create_text_channel(ch_name)

    summary = (
        f"팀 '{team_name}' 추가 완료 (프로젝트: {project_name})\n"
        f"카테고리: {new_category_name}\n"
        f"채널 {len(channels)}개 생성됨"
    )
    return [types.TextContent(type="text", text=summary)]


async def handle_add_channel(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    project_name = arguments["project_name"]
    team_name = arguments["team_name"]
    channel_name = arguments["channel_name"]

    # 카테고리 검색
    target_name = f"{project_name} / {team_name}"
    category = next(
        (c for c in guild.categories if c.name == target_name), None
    )
    if category is None:
        raise ValueError(
            f"카테고리 '{target_name}'를 찾을 수 없습니다"
        )

    # 채널 중복 확인
    if any(ch.name == channel_name for ch in category.channels):
        raise ValueError(f"채널 '{channel_name}'이(가) 이미 존재합니다")

    await category.create_text_channel(channel_name)

    summary = (
        f"채널 '{channel_name}' 생성 완료\n"
        f"위치: {target_name}"
    )
    return [types.TextContent(type="text", text=summary)]


async def handle_delete_project(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    project_name = arguments["project_name"]
    prefix = f"{project_name} / "

    targets = [c for c in guild.categories if c.name.startswith(prefix)]
    if not targets:
        raise ValueError(f"프로젝트 '{project_name}'를 찾을 수 없습니다")

    deleted_channels = 0
    for category in targets:
        for channel in category.channels:
            await channel.delete()
            deleted_channels += 1
        await category.delete()

    summary = (
        f"프로젝트 '{project_name}' 삭제 완료\n"
        f"카테고리 {len(targets)}개, 채널 {deleted_channels}개 삭제됨"
    )
    return [types.TextContent(type="text", text=summary)]


async def handle_list_projects(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    projects: dict[str, list[str]] = {}

    for category in guild.categories:
        if " / " not in category.name:
            continue
        project_name, team_name = category.name.split(" / ", 1)
        projects.setdefault(project_name, []).append(team_name)

    if not projects:
        return [types.TextContent(type="text", text="등록된 프로젝트가 없습니다")]

    return [types.TextContent(type="text", text=json.dumps(projects, ensure_ascii=False, indent=2))]


async def handle_send_notification(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    project_name = arguments["project_name"]
    message = arguments["message"]
    event_type = arguments["event_type"]

    if event_type not in NOTIFICATION_TYPES:
        raise ValueError(f"알 수 없는 event_type: {event_type}")

    # 프로젝트 내 claude-알림 채널 검색
    prefix = f"{project_name} / "
    notification_channel = None
    for category in guild.categories:
        if not category.name.startswith(prefix):
            continue
        for channel in category.channels:
            if "claude-알림" in channel.name:
                notification_channel = channel
                break
        if notification_channel:
            break

    if notification_channel is None:
        raise ValueError(
            f"프로젝트 '{project_name}'에서 claude-알림 채널을 찾을 수 없습니다"
        )

    # Embed 생성
    nt = NOTIFICATION_TYPES[event_type]
    embed = discord.Embed(
        title=f"{nt['emoji']} {nt['label']}",
        description=message,
        color=nt["color"],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    await notification_channel.send(embed=embed)

    return [types.TextContent(
        type="text",
        text=f"알림 전송 완료 [{nt['label']}] → {notification_channel.name}",
    )]


async def handle_send_message(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    project_name = arguments["project_name"]
    keyword = arguments["channel_keyword"]
    content = arguments["content"]

    channel = find_channel(guild, project_name, keyword)
    if channel is None:
        raise ValueError(
            f"프로젝트 '{project_name}'에서 '{keyword}' 채널을 찾을 수 없습니다"
        )

    await channel.send(content)

    return [types.TextContent(
        type="text",
        text=f"메시지 전송 완료 → {channel.name}",
    )]


async def handle_read_messages(arguments: dict[str, Any]) -> list[types.TextContent]:
    guild = get_guild()
    project_name = arguments["project_name"]
    keyword = arguments["channel_keyword"]
    limit = arguments.get("limit", 10)

    channel = find_channel(guild, project_name, keyword)
    if channel is None:
        raise ValueError(
            f"프로젝트 '{project_name}'에서 '{keyword}' 채널을 찾을 수 없습니다"
        )

    messages = []
    async for msg in channel.history(limit=limit):
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
        messages.append(f"[{timestamp}] {msg.author.display_name}: {msg.content}")

    if not messages:
        return [types.TextContent(type="text", text="메시지가 없습니다")]

    return [types.TextContent(type="text", text="\n".join(messages))]


# 도구 이름 → 핸들러 매핑
TOOL_HANDLERS = {
    "create_project": handle_create_project,
    "add_team": handle_add_team,
    "add_channel": handle_add_channel,
    "delete_project": handle_delete_project,
    "list_projects": handle_list_projects,
    "send_notification": handle_send_notification,
    "send_message": handle_send_message,
    "read_messages": handle_read_messages,
}


@server.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return [types.TextContent(type="text", text=f"알 수 없는 도구: {name}")]
    try:
        return await handler(arguments)
    except Exception as e:
        return [types.TextContent(type="text", text=f"오류 발생: {e}")]


# ---------------------------------------------------------------------------
# 메인 진입점
# ---------------------------------------------------------------------------

async def main():
    # Discord 봇을 백그라운드 태스크로 실행
    bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))

    # 봇이 준비될 때까지 대기
    await bot.wait_until_ready()

    # MCP 서버 실행 (stdio 트랜스포트)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="project-bot",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
