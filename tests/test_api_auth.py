"""API Key 인증 미들웨어 테스트"""

import os

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_GUILD_ID", "123456789")

from unittest.mock import patch

from starlette.testclient import TestClient

from server import starlette_app


class TestAPIKeyMiddleware:
    def test_mcp_endpoint_no_auth_required(self):
        """MCP 엔드포인트는 인증 없이 접근 가능"""
        client = TestClient(starlette_app, raise_server_exceptions=False)
        response = client.get("/mcp")
        assert response.status_code != 401

    def test_api_missing_key_returns_401(self):
        """API Key 없이 /api 접근 시 401"""
        with patch("server.API_KEY", "test-secret-key"):
            client = TestClient(starlette_app, raise_server_exceptions=False)
            response = client.get("/api/sessions")
        assert response.status_code == 401
        assert "API Key가 필요합니다" in response.json()["error"]

    def test_api_wrong_key_returns_401(self):
        """잘못된 API Key로 /api 접근 시 401"""
        with patch("server.API_KEY", "test-secret-key"):
            client = TestClient(starlette_app, raise_server_exceptions=False)
            response = client.get(
                "/api/sessions", headers={"X-API-Key": "wrong-key"}
            )
        assert response.status_code == 401
        assert "유효하지 않은" in response.json()["error"]

    def test_api_correct_key_passes(self):
        """올바른 API Key로 /api 접근 시 인증 통과"""
        with patch("server.API_KEY", "test-secret-key"):
            client = TestClient(starlette_app, raise_server_exceptions=False)
            response = client.get(
                "/api/sessions", headers={"X-API-Key": "test-secret-key"}
            )
        # 인증 통과 → 401이 아님 (라우트 미등록이면 404)
        assert response.status_code != 401

    def test_api_key_not_configured_returns_503(self):
        """서버에 API_KEY 미설정 시 503"""
        with patch("server.API_KEY", None):
            client = TestClient(starlette_app, raise_server_exceptions=False)
            response = client.get(
                "/api/sessions", headers={"X-API-Key": "any-key"}
            )
        assert response.status_code == 503
        assert "설정되지 않았습니다" in response.json()["error"]
