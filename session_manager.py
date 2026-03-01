"""유저별 대화 세션 관리 모듈"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List


@dataclass
class ConversationSession:
    """유저별 대화 세션"""

    user_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    session_id: str | None = None  # Claude Code --resume 용

    def add_message(self, role: str, content: str):
        """메시지 추가"""
        self.messages.append({"role": role, "content": content})
        self.last_activity = datetime.now()

    def get_messages(self, max_messages: int = 50) -> List[Dict[str, str]]:
        """최근 N개 메시지 반환"""
        return self.messages[-max_messages:]

    def clear(self):
        """대화 히스토리 초기화"""
        self.messages.clear()
        self.session_id = None
        self.last_activity = datetime.now()


class SessionManager:
    """전역 세션 관리자"""

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(self, user_id: str) -> ConversationSession:
        """세션 조회 또는 생성"""
        if user_id not in self._sessions:
            self._sessions[user_id] = ConversationSession(user_id=user_id)
        return self._sessions[user_id]

    def delete_session(self, user_id: str):
        """세션 삭제"""
        self._sessions.pop(user_id, None)

    def cleanup_old_sessions(self, hours: int = 24) -> int:
        """오래된 세션 정리. 삭제된 세션 수 반환"""
        cutoff = datetime.now() - timedelta(hours=hours)
        to_delete = [
            uid
            for uid, session in self._sessions.items()
            if session.last_activity < cutoff
        ]
        for uid in to_delete:
            del self._sessions[uid]
        return len(to_delete)

    @property
    def active_count(self) -> int:
        """활성 세션 수"""
        return len(self._sessions)


# 전역 인스턴스
session_manager = SessionManager()
