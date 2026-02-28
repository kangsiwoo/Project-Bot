# 아키텍처

Project Bot의 시스템 구조와 설계 원칙을 설명합니다.

---

## 시스템 개요

Project Bot은 **단일 프로세스** 안에서 MCP 서버와 Discord 봇이 동시에 동작하는 구조입니다.

```
┌──────────────────┐    stdio (JSON-RPC)    ┌─────────────────────┐
│   Claude Code    │ ◄─────────────────────► │   Project Bot       │
│   (MCP Client)   │                        │   (MCP Server)      │
└──────────────────┘                        │                     │
                                            │ ┌─────────────────┐ │
 CLAUDE.md 규칙:                             │ │ discord.py Bot  │ │
 "매 턴마다 send_notification 호출"          │ │ (백그라운드)     │ │
                                            │ └────────┬────────┘ │
 Stop 훅 (백업):                             └──────────┼──────────┘
 MCP 누락 시 웹훅 직접 전송                             │
                                            ┌──────────▼──────────┐
                                            │   Discord Server    │
                                            │  📁 project / 팀    │
                                            │  🤖-claude-알림     │
                                            └─────────────────────┘
```

---

## 컴포넌트

### MCP Server (`server.py`)

- `mcp.server.lowlevel.Server` 기반
- stdio 트랜스포트로 Claude Code와 JSON-RPC 통신
- 8개 도구(Tool) 등록 및 호출 처리
- `call_tool` 디스패처가 도구명으로 핸들러 라우팅

### Discord Bot (`discord.py`)

- `discord.Client`로 Discord Gateway에 연결
- `asyncio.create_task`로 백그라운드 실행
- Guild(서버) 객체를 통해 카테고리/채널 CRUD 수행
- Embed 메시지 전송 지원

### 설정 (`config.py`)

- `DEFAULT_TEAMS`: 기본 5개 팀 채널 템플릿
- `CUSTOM_TEAM_CHANNELS`: 커스텀 팀용 채널 패턴
- `NOTIFICATION_TYPES`: event_type별 색상/이모지/라벨

---

## asyncio 이벤트 루프

단일 이벤트 루프에서 두 가지 비동기 작업이 동시에 실행됩니다:

```python
async def main():
    # 1) Discord 봇을 백그라운드 태스크로 실행
    bot_task = asyncio.create_task(bot.start(DISCORD_TOKEN))

    # 2) 봇이 준비될 때까지 대기
    await bot.wait_until_ready()

    # 3) MCP 서버 메인 루프 (도구 호출 수신)
    async with stdio_server() as (read, write):
        await server.run(read, write, ...)
```

- **bot.start()**: Discord Gateway 연결을 유지하며 이벤트를 수신
- **server.run()**: stdin에서 JSON-RPC 메시지를 읽고 도구 호출을 처리
- 두 작업은 같은 이벤트 루프에서 협력적으로 스케줄링됨

---

## 통신 흐름

### 도구 호출 흐름

```
1. Claude Code가 "프로젝트 만들어줘" 요청
2. Claude가 create_project 도구 호출 결정
3. JSON-RPC 메시지가 stdio로 server.py에 전달
4. call_tool 디스패처 → handle_create_project 핸들러
5. 핸들러가 discord.py API로 카테고리/채널 생성
6. Discord API 응답 → 결과를 JSON-RPC로 Claude에 반환
```

### 채널 검색 흐름

```
프로젝트 카테고리 이름 규칙: "{project_name} / {team_name}"

1. guild.categories에서 prefix가 일치하는 카테고리 필터링
2. 카테고리 내 channels에서 keyword 매칭
3. 첫 번째 매칭 채널 반환
```

---

## 3중 알림 안전장치

| 단계 | 메커니즘 | 담당 |
|------|---------|------|
| 1차 | CLAUDE.md 규칙 | Claude가 매 턴 `send_notification` 호출 |
| 2차 | Stop 훅 | MCP 호출 누락 시 웹훅으로 백업 전송 |
| 3차 | 자동 프로젝트명 추출 | `$PWD` 디렉터리명으로 프로젝트 자동 감지 |

---

## Discord 채널 구조

### 카테고리 이름 규칙

```
{project_name} / {team_name}
```

예: `my-app / 프론트엔드`, `my-app / 공통`

이 규칙을 기반으로 `list_projects`가 프로젝트를 파싱하고, `delete_project`가 삭제 대상을 식별합니다.

### 기본 템플릿 (5팀, 15채널)

| 팀 | 채널 |
|----|------|
| 기획 | 📋-기획-일반, 📝-회의록, 🎯-마일스톤 |
| 프론트엔드 | 🖥-프론트-일반, 🐛-프론트-이슈, 📦-프론트-빌드 |
| 백엔드 | ⚙-백엔드-일반, 🐛-백엔드-이슈, 🗄-데이터베이스 |
| 인프라 | ☁-인프라-일반, 🔧-ci-cd, 📊-모니터링 |
| 공통 | 🤖-claude-알림, 📢-공지사항, 💬-자유톡 |

### 커스텀 팀

기본 템플릿에 없는 팀명은 2개 채널이 자동 생성됩니다:
- `💬-{팀명}-일반`
- `🐛-{팀명}-이슈`

---

## 확장 가능성

- **멀티 플랫폼**: `config.py`에 Slack/Telegram 어댑터 추가
- **채널 템플릿 커스터마이즈**: JSON 기반 외부 설정 파일 지원
- **승인 워크플로우**: Discord 리액션 기반 승인/거절 시스템
- **채널별 알림 라우팅**: event_type에 따른 자동 분기
