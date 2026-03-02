# 설치 가이드

Project Bot을 설치하고 Claude Code에 연동하는 방법을 안내합니다.

---

## 사전 요구사항

- Python 3.10 이상
- pip 또는 uv
- Discord 계정 및 서버 관리 권한
- Claude Code CLI

---

## 1단계: Discord Bot 생성

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 **New Application** 클릭
2. 이름 입력 후 **Create**
3. **Bot** 탭으로 이동
   - **Reset Token** 클릭 → 토큰 복사 (이후 다시 볼 수 없음)
   - **Privileged Gateway Intents** 전부 활성화:
     - Presence Intent
     - Server Members Intent
     - Message Content Intent
4. **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator`
5. 생성된 URL을 브라우저에 붙여넣고 봇을 서버에 초대

---

## 2단계: 의존성 설치

```bash
# 저장소 클론
git clone https://github.com/kangsiwoo/Project-Bot.git
cd project-bot

# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

uv 사용 시:

```bash
uv pip install -r requirements.txt
```

---

## 3단계: 서버 실행

환경 변수를 설정하고 서버를 실행합니다. Discord 봇과 MCP HTTP 서버가 동시에 시작됩니다.

```bash
export DISCORD_TOKEN=봇토큰여기
export DISCORD_GUILD_ID=서버ID여기
python server.py
```

서버가 정상 시작되면:
- Discord 봇이 온라인 상태로 전환됩니다
- MCP HTTP 서버가 `http://localhost:8080/mcp`에서 대기합니다

**DISCORD_GUILD_ID 확인 방법:**
1. Discord 설정 → 고급 → 개발자 모드 활성화
2. 서버 이름 우클릭 → **서버 ID 복사**

---

## 4단계: Claude Code에 MCP 서버 등록

서버가 실행 중인 상태에서 별도 터미널에서 등록합니다:

```bash
claude mcp add project-bot --transport http http://localhost:8080/mcp
```

---

## 5단계: Stop 훅 설정 (백업 알림)

```bash
# 프로젝트 디렉터리에 설정 파일 복사
mkdir -p .claude/hooks
cp project-bot/.claude/hooks/project-bot-stop-hook.sh .claude/hooks/
cp project-bot/.claude/CLAUDE.md .claude/CLAUDE.md
chmod +x .claude/hooks/*.sh
```

### Discord 웹훅 URL 생성

1. Discord 서버 → claude-알림 채널 → 설정 (톱니바퀴)
2. **연동** → **웹훅** → **새 웹훅**
3. 웹훅 URL 복사
4. 환경변수 설정:

```bash
export DISCORD_WEBHOOK_URL="복사한_웹훅_URL"
```

---

## 6단계: 동작 확인

Claude Code에서 다음과 같이 테스트합니다:

```
"test-project라는 프로젝트를 디스코드에 만들어줘"
```

정상 동작 시:
- Discord 서버에 5개 카테고리, 15개 채널이 생성됩니다
- `test-project / 공통` 카테고리 아래 `🤖-claude-알림` 채널이 포함됩니다

테스트 후 정리:

```
"test-project 프로젝트를 삭제해줘"
```

---

## 테스트 실행

```bash
# 가상환경 활성화 후
source .venv/bin/activate

# 전체 테스트 실행
python -m pytest tests/ -v
```

### 알려진 Warnings

테스트 실행 시 아래 2개의 warning이 발생할 수 있으며, **모두 외부 라이브러리 이슈로 코드에 영향 없습니다.**

| Warning | 원인 | 영향 |
|---------|------|------|
| `DeprecationWarning: 'audioop' is deprecated` | discord.py 내부에서 Python 3.13 제거 예정인 `audioop` 모듈 사용 | 없음 (음성 기능 미사용) |
| `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` | 무시 시나리오 테스트에서 AsyncMock이 호출되지 않을 때 발생 | 없음 (테스트 결과 정상) |

---

## 트러블슈팅

### `Guild ID를 찾을 수 없습니다`

- DISCORD_GUILD_ID가 올바른지 확인
- 봇이 해당 서버에 초대되었는지 확인
- Privileged Gateway Intents가 활성화되어 있는지 확인

### `mcp 패키지 설치 실패`

- Python 3.10 이상인지 확인: `python3 --version`
- pip를 최신 버전으로 업그레이드: `pip install --upgrade pip`

### `봇이 오프라인으로 표시됨`

- DISCORD_TOKEN이 올바른지 확인
- 토큰을 재발급해야 할 수 있음 (Developer Portal → Bot → Reset Token)

### `채널 생성 권한 오류`

- 봇에 Administrator 권한이 부여되었는지 확인
- OAuth2 URL을 다시 생성하여 봇을 재초대
