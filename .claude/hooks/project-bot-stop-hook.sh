#!/usr/bin/env bash
# project-bot-stop-hook.sh
# Claude Code Stop 훅 - MCP send_notification 누락 시 웹훅으로 백업 알림 전송
# 3중 알림 안전장치 중 2차 담당

set -euo pipefail

# 환경변수 확인
WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
if [ -z "$WEBHOOK_URL" ]; then
    exit 0
fi

# 프로젝트명: 환경변수 또는 현재 디렉터리명
PROJECT_NAME="${PROJECT_NAME:-$(basename "$PWD")}"

# stdin으로 전달된 transcript에서 send_notification 호출 여부 확인
TRANSCRIPT=$(cat)

if echo "$TRANSCRIPT" | grep -q "send_notification"; then
    # MCP로 이미 알림을 보냈으면 중복 전송하지 않음
    exit 0
fi

# MCP 호출이 없었으면 웹훅으로 백업 알림 전송
PAYLOAD=$(cat <<ENDJSON
{
  "embeds": [{
    "title": "MCP 백업 알림",
    "description": "Claude Code 턴이 종료되었지만 MCP send_notification 호출이 감지되지 않았습니다.",
    "color": 9807270,
    "fields": [
      {
        "name": "프로젝트",
        "value": "$PROJECT_NAME",
        "inline": true
      }
    ]
  }]
}
ENDJSON
)

curl -s -H "Content-Type: application/json" -d "$PAYLOAD" "$WEBHOOK_URL" > /dev/null 2>&1 || true
