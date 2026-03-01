"""session_manager 단위 테스트"""

import time
from datetime import datetime, timedelta

from session_manager import ConversationSession, SessionManager


class TestConversationSession:
    def test_add_message(self):
        session = ConversationSession(user_id="user1")
        session.add_message("user", "안녕하세요")
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "안녕하세요"

    def test_get_messages_limit(self):
        session = ConversationSession(user_id="user1")
        for i in range(100):
            session.add_message("user", f"메시지 {i}")
        messages = session.get_messages(max_messages=50)
        assert len(messages) == 50
        assert messages[0]["content"] == "메시지 50"
        assert messages[-1]["content"] == "메시지 99"

    def test_get_messages_under_limit(self):
        session = ConversationSession(user_id="user1")
        session.add_message("user", "하나")
        session.add_message("assistant", "둘")
        messages = session.get_messages(max_messages=50)
        assert len(messages) == 2

    def test_clear(self):
        session = ConversationSession(user_id="user1")
        session.session_id = "abc-123"
        session.add_message("user", "테스트")
        session.clear()
        assert len(session.messages) == 0
        assert session.session_id is None

    def test_last_activity_updated(self):
        session = ConversationSession(user_id="user1")
        before = session.last_activity
        time.sleep(0.01)
        session.add_message("user", "메시지")
        assert session.last_activity > before


class TestSessionManager:
    def test_create_session(self):
        manager = SessionManager()
        session = manager.get_or_create_session("user1")
        assert session.user_id == "user1"
        assert len(session.messages) == 0

    def test_get_existing_session(self):
        manager = SessionManager()
        session1 = manager.get_or_create_session("user1")
        session1.add_message("user", "기존 메시지")
        session2 = manager.get_or_create_session("user1")
        assert session1 is session2
        assert len(session2.messages) == 1

    def test_separate_sessions(self):
        manager = SessionManager()
        s1 = manager.get_or_create_session("user1")
        s2 = manager.get_or_create_session("user2")
        s1.add_message("user", "유저1 메시지")
        assert len(s2.messages) == 0

    def test_delete_session(self):
        manager = SessionManager()
        manager.get_or_create_session("user1")
        manager.delete_session("user1")
        assert manager.active_count == 0

    def test_delete_nonexistent(self):
        manager = SessionManager()
        manager.delete_session("없는유저")  # 에러 없이 통과

    def test_cleanup_old_sessions(self):
        manager = SessionManager()
        old = manager.get_or_create_session("old_user")
        old.last_activity = datetime.now() - timedelta(hours=25)
        manager.get_or_create_session("new_user")
        deleted = manager.cleanup_old_sessions(hours=24)
        assert deleted == 1
        assert manager.active_count == 1

    def test_cleanup_no_old_sessions(self):
        manager = SessionManager()
        manager.get_or_create_session("user1")
        deleted = manager.cleanup_old_sessions(hours=24)
        assert deleted == 0
        assert manager.active_count == 1

    def test_active_count(self):
        manager = SessionManager()
        assert manager.active_count == 0
        manager.get_or_create_session("user1")
        manager.get_or_create_session("user2")
        assert manager.active_count == 2
