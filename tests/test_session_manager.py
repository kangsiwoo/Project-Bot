"""session_manager 단위 테스트"""

import time
from datetime import datetime, timedelta

from session_manager import ConversationSession, SessionManager


class TestConversationSession:
    def test_add_message(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        session.add_message("user", "안녕하세요")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "안녕하세요"

    def test_get_recent_messages_limit(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        for i in range(100):
            session.add_message("user", f"메시지 {i}")
        messages = session.get_recent_messages(limit=50)
        assert len(messages) == 50
        assert messages[0]["content"] == "메시지 50"
        assert messages[-1]["content"] == "메시지 99"

    def test_get_recent_messages_under_limit(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        session.add_message("user", "하나")
        session.add_message("assistant", "둘")
        messages = session.get_recent_messages(limit=50)
        assert len(messages) == 2

    def test_clear(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        session.add_message("user", "테스트")
        session.clear()
        assert len(session.messages) == 0

    def test_last_activity_updated(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        before = session.last_activity
        time.sleep(0.01)
        session.add_message("user", "메시지")
        assert session.last_activity > before

    def test_to_dict_basic(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        session.add_message("user", "hello")
        d = session.to_dict()
        assert d["channel_id"] == "ch1"
        assert d["user_id"] == "user1"
        assert d["message_count"] == 1
        assert "created_at" in d
        assert "last_activity" in d
        assert "recent_messages" not in d

    def test_to_dict_with_messages(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        session.add_message("user", "안녕")
        session.add_message("assistant", "반갑습니다")
        d = session.to_dict(message_limit=10)
        assert d["message_count"] == 2
        assert len(d["recent_messages"]) == 2
        assert d["recent_messages"][0]["content"] == "안녕"

    def test_to_dict_zero_limit(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        session.add_message("user", "test")
        d = session.to_dict(message_limit=0)
        assert "recent_messages" not in d

    def test_to_dict_datetime_format(self):
        session = ConversationSession(channel_id="ch1", user_id="user1")
        d = session.to_dict()
        # ISO 형식 검증
        datetime.fromisoformat(d["created_at"])
        datetime.fromisoformat(d["last_activity"])


class TestSessionManager:
    def test_create_session(self):
        manager = SessionManager()
        session = manager.get_or_create_session("ch1", "user1")
        assert session.channel_id == "ch1"
        assert session.user_id == "user1"
        assert len(session.messages) == 0

    def test_get_existing_session(self):
        manager = SessionManager()
        session1 = manager.get_or_create_session("ch1", "user1")
        session1.add_message("user", "기존 메시지")
        session2 = manager.get_or_create_session("ch1", "user1")
        assert session1 is session2
        assert len(session2.messages) == 1

    def test_separate_sessions_by_channel(self):
        manager = SessionManager()
        s1 = manager.get_or_create_session("ch1", "user1")
        s2 = manager.get_or_create_session("ch2", "user1")
        s1.add_message("user", "채널1 메시지")
        assert len(s2.messages) == 0

    def test_same_user_multiple_channels(self):
        """같은 유저가 여러 채널에서 별도의 세션을 가진다"""
        manager = SessionManager()
        s1 = manager.get_or_create_session("console-alice", "alice")
        s2 = manager.get_or_create_session("project-frontend", "alice")
        s1.add_message("user", "콘솔 메시지")
        s2.add_message("user", "프론트 메시지")
        assert len(s1.messages) == 1
        assert len(s2.messages) == 1
        assert s1.messages[0]["content"] == "콘솔 메시지"
        assert s2.messages[0]["content"] == "프론트 메시지"

    def test_delete_session(self):
        manager = SessionManager()
        manager.get_or_create_session("ch1", "user1")
        manager.delete_session("ch1")
        assert manager.active_count == 0

    def test_delete_nonexistent(self):
        manager = SessionManager()
        manager.delete_session("없는채널")  # 에러 없이 통과

    def test_cleanup_old_sessions(self):
        manager = SessionManager()
        old = manager.get_or_create_session("old_ch", "old_user")
        old.last_activity = datetime.now() - timedelta(hours=25)
        manager.get_or_create_session("new_ch", "new_user")
        deleted = manager.cleanup_old_sessions(hours=24)
        assert deleted == 1
        assert manager.active_count == 1

    def test_cleanup_no_old_sessions(self):
        manager = SessionManager()
        manager.get_or_create_session("ch1", "user1")
        deleted = manager.cleanup_old_sessions(hours=24)
        assert deleted == 0
        assert manager.active_count == 1

    def test_active_count(self):
        manager = SessionManager()
        assert manager.active_count == 0
        manager.get_or_create_session("ch1", "user1")
        manager.get_or_create_session("ch2", "user2")
        assert manager.active_count == 2

    def test_get_session_existing(self):
        manager = SessionManager()
        manager.get_or_create_session("ch1", "user1")
        session = manager.get_session("ch1")
        assert session is not None
        assert session.channel_id == "ch1"
        assert session.user_id == "user1"

    def test_get_session_not_found(self):
        manager = SessionManager()
        assert manager.get_session("없는채널") is None

    def test_list_sessions_returns_copy(self):
        manager = SessionManager()
        manager.get_or_create_session("ch1", "user1")
        manager.get_or_create_session("ch2", "user2")
        sessions = manager.list_sessions()
        assert len(sessions) == 2
        assert "ch1" in sessions
        # 반환된 딕셔너리를 변경해도 원본에 영향 없음
        sessions.pop("ch1")
        assert manager.active_count == 2

    def test_list_sessions_empty(self):
        manager = SessionManager()
        sessions = manager.list_sessions()
        assert sessions == {}
