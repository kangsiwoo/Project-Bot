"""세션 관리 REST API 엔드포인트 테스트"""

import os

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

from datetime import datetime, timedelta
from unittest.mock import patch

from starlette.testclient import TestClient

from server import starlette_app
from session_manager import SessionManager

API_HEADERS = {"X-API-Key": "test-key"}


def _client():
    return TestClient(starlette_app, raise_server_exceptions=False)


class TestListSessions:
    def test_empty(self):
        sm = SessionManager()
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().get("/api/sessions", headers=API_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_count"] == 0
        assert data["sessions"] == []

    def test_multiple_sessions(self):
        sm = SessionManager()
        sm.get_or_create_session("user1").add_message("user", "hello")
        sm.get_or_create_session("user2")
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().get("/api/sessions", headers=API_HEADERS)
        data = resp.json()
        assert data["active_count"] == 2
        assert len(data["sessions"]) == 2
        user_ids = {s["user_id"] for s in data["sessions"]}
        assert user_ids == {"user1", "user2"}

    def test_session_fields(self):
        sm = SessionManager()
        sm.get_or_create_session("user1").add_message("user", "hi")
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().get("/api/sessions", headers=API_HEADERS)
        session = resp.json()["sessions"][0]
        assert "user_id" in session
        assert "message_count" in session
        assert "created_at" in session
        assert "last_activity" in session
        assert session["message_count"] == 1


class TestGetSession:
    def test_success(self):
        sm = SessionManager()
        sm.get_or_create_session("user1").add_message("user", "안녕")
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().get("/api/sessions/user1", headers=API_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "user1"
        assert data["message_count"] == 1
        assert len(data["recent_messages"]) == 1

    def test_not_found(self):
        sm = SessionManager()
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().get("/api/sessions/없는유저", headers=API_HEADERS)
        assert resp.status_code == 404
        assert "찾을 수 없습니다" in resp.json()["error"]

    def test_message_limit(self):
        sm = SessionManager()
        s = sm.get_or_create_session("user1")
        for i in range(30):
            s.add_message("user", f"msg{i}")
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().get(
                "/api/sessions/user1?message_limit=5", headers=API_HEADERS
            )
        data = resp.json()
        assert len(data["recent_messages"]) == 5
        assert data["recent_messages"][0]["content"] == "msg25"


class TestDeleteSession:
    def test_success(self):
        sm = SessionManager()
        sm.get_or_create_session("user1")
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().delete("/api/sessions/user1", headers=API_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user1"
        assert sm.active_count == 0

    def test_not_found(self):
        sm = SessionManager()
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().delete("/api/sessions/없는유저", headers=API_HEADERS)
        assert resp.status_code == 404


class TestCleanupSessions:
    def test_cleanup_old(self):
        sm = SessionManager()
        old = sm.get_or_create_session("old_user")
        old.last_activity = datetime.now() - timedelta(hours=25)
        sm.get_or_create_session("new_user")
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().post(
                "/api/sessions/cleanup",
                headers=API_HEADERS,
                json={"hours": 24},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] == 1
        assert data["remaining_active"] == 1

    def test_cleanup_default_hours(self):
        sm = SessionManager()
        sm.get_or_create_session("user1")
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().post(
                "/api/sessions/cleanup", headers=API_HEADERS
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] == 0
        assert data["remaining_active"] == 1

    def test_cleanup_custom_hours(self):
        sm = SessionManager()
        s = sm.get_or_create_session("user1")
        s.last_activity = datetime.now() - timedelta(hours=2)
        with patch("server.API_KEY", "test-key"), patch("server.session_manager", sm):
            resp = _client().post(
                "/api/sessions/cleanup",
                headers=API_HEADERS,
                json={"hours": 1},
            )
        assert resp.json()["deleted_count"] == 1
