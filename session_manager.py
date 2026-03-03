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

    def add_message(self, role: str, content: str):
        """메시지 추가"""
        self.messages.append({"role": role, "content": content})
        self.last_activity = datetime.now()

    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, str]]:
        """최근 N개 메시지 반환"""
        return self.messages[-limit:]

    def clear(self):
        """대화 히스토리 초기화"""
        self.messages.clear()
        self.last_activity = datetime.now()

    def to_dict(self, message_limit: int = 0) -> dict:
        """세션 정보를 딕셔너리로 직렬화한다.

        Args:
            message_limit: 포함할 최근 메시지 수. 0이면 메시지 미포함.
        """
        data = {
            "user_id": self.user_id,
            "message_count": len(self.messages),
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }
        if message_limit > 0:
            data["recent_messages"] = self.get_recent_messages(limit=message_limit)
        return data


class SessionManager:
    """전역 세션 관리자"""

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create_session(self, user_id: str) -> ConversationSession:
        """세션 조회 또는 생성"""
        if user_id not in self._sessions:
            self._sessions[user_id] = ConversationSession(user_id=user_id)
        return self._sessions[user_id]

    def get_session(self, user_id: str):
        """세션 조회. 존재하지 않으면 None 반환."""
        return self._sessions.get(user_id)

    def list_sessions(self) -> Dict[str, "ConversationSession"]:
        """모든 세션의 얕은 복사본 반환."""
        return dict(self._sessions)

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
