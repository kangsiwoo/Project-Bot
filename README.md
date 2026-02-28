# 🤖 Project Bot

**Project Bot**은 Claude Code에서 MCP 도구로 직접 호출하여 Discord 프로젝트를 관리하고 알림을 보내는 MCP 서버입니다.

Python의 `mcp` SDK와 `discord.py`를 결합하여, 하나의 stdio 프로세스 안에서 Discord 봇과 MCP 서버가 동시에 동작합니다. Claude Code가 `claude mcp add` 명령으로 등록하면 즉시 사용 가능합니다.

---

## ✨ 주요 기능

### 🎯 프로젝트 관리
- **프로젝트 생성**: Discord 서버에 카테고리와 채널 일괄 생성
- **팀 추가**: 기존 프로젝트에 새로운 팀 카테고리 추가
- **채널 관리**: 특정 팀에 채널 추가/삭제
- **프로젝트 조회**: 등록된 모든 프로젝트 목록 조회

### 📢 알림 및 메시징
- **알림 전송**: 프로젝트별 전용 채널(`claude-알림`)에 Embed 형식 알림
- **메시지 전송**: 특정 채널에 직접 메시지 전송
- **메시지 읽기**: 특정 채널의 최근 메시지 조회

### 🔒 안정성
- **3중 알림 안전장치**
  - 1차: CLAUDE.md 규칙 (Claude가 매 턴마다 `send_notification` 호출)
  - 2차: Stop 훅 (MCP 호출 누락 시 웹훅으로 백업 전송)
  - 3차: 자동 프로젝트명 추출 (디렉터리명으로 자동 감지)

---

## 🏗️ 아키텍처

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

MCP 서버는 stdio 트랜스포트를 사용하여 Claude Code와 JSON-RPC로 통신합니다. 내부적으로 `asyncio.create_task`로 Discord 봇을 백그라운드에 실행하고, MCP 서버 메인 루프는 stdio를 통해 도구 호출을 수신합니다.

---

## 📋 MCP 도구 목록

| 도구 | 설명 | 파라미터 |
|------|------|---------|
| `create_project` | 프로젝트 카테고리 + 채널 일괄 생성 | `project_name`, `teams`(선택) |
| `add_team` | 기존 프로젝트에 팀 카테고리 추가 | `project_name`, `team_name` |
| `add_channel` | 특정 팀에 채널 추가 | `project_name`, `team_name`, `channel_name` |
| `delete_project` | 프로젝트 전체 삭제 | `project_name` |
| `list_projects` | 등록된 프로젝트 조회 | (없음) |
| `send_notification` | claude-알림 채널에 Embed 전송 | `project_name`, `message`, `event_type` |
| `send_message` | 특정 채널에 일반 메시지 전송 | `project_name`, `channel_keyword`, `content` |
| `read_messages` | 특정 채널의 최근 메시지 읽기 | `project_name`, `channel_keyword`, `limit` |

### send_notification의 event_type

| event_type | 설명 | 색상 |
|-----------|------|------|
| `plan` | 플랜 작성 | 🔵 파란색 |
| `question` | 질문 제시 | 🟠 주황색 |
| `complete` | 작업 완료 | 🟢 초록색 |
| `error` | 에러 발생 | 🔴 빨간색 |
| `build` | 빌드 진행 | 보라색 |
| `test` | 테스트 진행 | 노란색 |
| `deploy` | 배포 진행 | 분홍색 |

---

## 📁 Discord 채널 구조

`create_project` 도구를 호출하면 아래와 같은 구조가 자동 생성됩니다.

### 기본 템플릿 (5개 팀)

```
📁 my-app / 기획
  ├── 📋-기획-일반
  ├── 📝-회의록
  └── 🎯-마일스톤

📁 my-app / 프론트엔드
  ├── 🖥-프론트-일반
  ├── 🐛-프론트-이슈
  └── 📦-프론트-빌드

📁 my-app / 백엔드
  ├── ⚙-백엔드-일반
  ├── 🐛-백엔드-이슈
  └── 🗄-데이터베이스

📁 my-app / 인프라
  ├── ☁-인프라-일반
  ├── 🔧-ci-cd
  └── 📊-모니터링

📁 my-app / 공통
  ├── 🤖-claude-알림    ← Claude Code 알림 수신
  ├── 📢-공지사항
  └── 💬-자유톡
```

### 커스텀 팀

기본 템플릿에 없는 팀명(예: `QA`, `디자인`)을 지정하면:
- `💬-{팀명}-일반`
- `🐛-{팀명}-이슈`

두 개 채널이 자동 생성됩니다.

---

## 🚀 설치 및 설정

### 1단계: Discord Bot 생성

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 New Application 생성
2. **Bot** 탭 → **Reset Token** → 토큰 복사
3. **Privileged Gateway Intents** 활성화:
   - Presence Intent
   - Server Members Intent
   - Message Content Intent
4. **OAuth2** → **URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Administrator`
5. 생성된 URL로 디스코드 서버에 봇 초대

### 2단계: 의존성 설치

```bash
pip install discord.py mcp
```

또는 uv 사용 시:

```bash
uv pip install discord.py mcp
```

### 3단계: Claude Code에 MCP 서버 등록

```bash
claude mcp add --transport stdio \
  --env DISCORD_TOKEN=봇토큰여기 \
  --env DISCORD_GUILD_ID=서버ID여기 \
  project-bot -- python /path/to/project-bot/server.py
```

이 명령 하나로 Claude Code가 Project Bot의 8개 도구를 인식하고 사용할 수 있게 됩니다.

### 4단계: Stop 훅 설정 (백업 알림)

```bash
mkdir -p .claude/hooks
cp project-bot-stop-hook.sh .claude/hooks/
cp settings.json .claude/settings.json
cp CLAUDE.md .claude/CLAUDE.md
chmod +x .claude/hooks/*.sh
```

Stop 훅에 필요한 `DISCORD_WEBHOOK_URL`은 Discord 채널 설정 → 통합 → 웹훅에서 생성합니다.

---

## 💡 사용 예시

### 프로젝트 생성

```
Claude Code에게:
"my-app이라는 프로젝트를 디스코드에 만들어줘"

→ Claude가 create_project(project_name="my-app") 호출
→ 5개 카테고리, 15개 채널 자동 생성
```

### 팀 추가

```
Claude Code에게:
"my-app에 QA 팀 추가해줘"

→ Claude가 add_team(project_name="my-app", team_name="QA") 호출
→ QA 팀 카테고리와 채널 자동 생성
```

### 알림 전송

```
Claude Code에게:
"my-app 프로젝트에서 기획 완료 알림 보내줘"

→ Claude가 send_notification(
    project_name="my-app",
    message="기획 완료",
    event_type="complete"
  ) 호출
→ my-app/claude-알림 채널에 초록색 Embed 메시지 전송
```

---

## 📁 프로젝트 구조

```
project-bot/
├── README.md                      # 이 파일
├── CONTRIBUTING.md                # 개발 가이드
├── DEVELOPMENT.md                 # 빠른 시작 가이드
├── server.py                      # MCP 서버 + Discord 봇 핵심 코드
├── config.py                      # Discord 채널 템플릿 설정
├── requirements.txt               # Python 의존성
├── .github/
│   ├── pull_request_template.md   # PR 템플릿
│   ├── commit_template.md         # 커밋 템플릿
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
├── .claude/
│   ├── CLAUDE.md                  # Claude Code 규칙 (알림 의무)
│   ├── settings.json              # Claude Code 설정
│   └── hooks/
│       └── project-bot-stop-hook.sh  # 백업 알림 훅
└── docs/
    ├── SETUP.md                   # 설치 가이드
    ├── ARCHITECTURE.md            # 아키텍처 상세 설명
    └── API.md                     # MCP 도구 API 문서
```

---

## 🛠️ 개발 가이드

### 로컬 개발 환경 세팅

```bash
# 저장소 클론
git clone https://github.com/kangsiwoo/Project-Bot.git
cd project-bot

# 브랜치 생성
git checkout -b feature/your-feature-name

# 개발
# ... 코드 작성 ...

# 커밋 및 푸시
git commit -m "feat(feature-name): 설명"
git push origin feature/your-feature-name

# PR 생성
# GitHub에서 PR 생성 후 리뷰 대기
```

자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md)와 [DEVELOPMENT.md](DEVELOPMENT.md)를 참고하세요.

---

## 📚 문서

- [설치 가이드](docs/SETUP.md) - 상세 설치 및 설정 방법
- [아키텍처](docs/ARCHITECTURE.md) - 시스템 아키텍처 및 설계
- [API 문서](docs/API.md) - MCP 도구별 상세 API 명세
- [개발 가이드](CONTRIBUTING.md) - Git 컨벤션 및 PR 프로세스
- [빠른 시작](DEVELOPMENT.md) - 개발자를 위한 체크리스트

---

## 🔄 이전 설계와의 차이점

| 항목 | 이전 (봇 + 훅 방식) | 현재 (MCP 방식) |
|------|---------------------|----------------|
| 실행 방식 | bot.py + 내장 HTTP 서버 | stdio MCP 서버 단일 프로세스 |
| Claude Code 연동 | 훅에서 HTTP POST | 직접 MCP 도구 호출 |
| 채널 관리 | 슬래시 커맨드 | MCP 도구 (Claude가 자연어로 호출) |
| 알림 보장 | 훅 단독 | CLAUDE.md + MCP + 훅 3중 구조 |
| 등록 방법 | 별도 실행 필요 | `claude mcp add` 한 줄 |
| 부가 기능 | 없음 | `read_messages`, `send_message` 추가 |

---

## 🚀 확장 가능한 기능

- **멀티 플랫폼 알림**: Telegram/Slack 병행 알림 지원 가능
- **승인 워크플로우**: Discord 리액션 기반 승인/거절 시스템
- **프로젝트 템플릿 커스터마이즈**: JSON 기반 채널 템플릿
- **채널별 알림 라우팅**: event_type에 따른 자동 분기

---

## 📝 라이선스

MIT

---

## 🤝 기여하기

Project Bot 개발에 기여하고 싶으신가요?

1. [CONTRIBUTING.md](CONTRIBUTING.md)에서 개발 컨벤션 확인
2. [DEVELOPMENT.md](DEVELOPMENT.md)에서 빠른 시작 가이드 확인
3. 기능별로 브랜치 생성 후 PR 제출
4. 팀원 리뷰 후 승인되면 머지

---

## 💬 질문 또는 건의

이슈를 생성하거나 토론을 시작해주세요!
- [🐛 버그 리포트](https://github.com/kangsiwoo/Project-Bot/issues/new?template=bug_report.md)
- [✨ 기능 요청](https://github.com/kangsiwoo/Project-Bot/issues/new?template=feature_request.md)
- [💭 토론](https://github.com/kangsiwoo/Project-Bot/discussions)

---

**Happy Coding! 🚀**
