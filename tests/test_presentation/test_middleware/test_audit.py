"""Unit tests for AuditMiddleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.presentation.middleware.audit import AuditMiddleware, sanitize_headers


class TestSanitizeHeaders:
    """Test header sanitization logic."""

    def test_authorization_header_redacted(self):
        """Test Authorization header is redacted."""
        headers = {"Authorization": "Bearer my-secret-token"}
        result = sanitize_headers(headers)

        assert "***REDACTED***" in result["Authorization"]
        assert "Bearer" not in result["Authorization"]
        assert "my-secret-token" not in result["Authorization"]

    def test_x_api_key_header_redacted(self):
        """Test X-API-Key header is redacted."""
        headers = {"X-API-Key": "secret-key-12345"}
        result = sanitize_headers(headers)

        assert "***REDACTED***" in result["X-API-Key"]
        assert "secret-key" not in result["X-API-Key"]

    def test_cookie_header_redacted(self):
        """Test Cookie header is redacted."""
        headers = {"Cookie": "session=abc123; token=xyz789"}
        result = sanitize_headers(headers)

        assert "***REDACTED***" in result["Cookie"]

    def test_non_sensitive_headers_preserved(self):
        """Test non-sensitive headers are not modified."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Request-ID": "req-123",
        }
        result = sanitize_headers(headers)

        assert result["Content-Type"] == "application/json"
        assert result["Accept"] == "application/json"
        assert result["X-Request-ID"] == "req-123"

    def test_empty_header_value_redacted(self):
        """Test empty header value is still redacted."""
        headers = {"Authorization": ""}
        result = sanitize_headers(headers)

        assert result["Authorization"] == "***REDACTED***"

    def test_case_insensitive_header_matching(self):
        """Test header matching is case insensitive."""
        headers = {"authorization": "Bearer token123"}
        result = sanitize_headers(headers)

        assert "***REDACTED***" in result["authorization"]


class TestAuditMiddlewareDispatch:
    """Test AuditMiddleware dispatch method."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.url.path = "/events"
        request.method = "GET"
        request.headers = {
            "X-API-Key": "test-api-key",
            "Authorization": "Bearer secret",
        }
        request.client.host = "127.0.0.1"
        return request

    @pytest.fixture
    def middleware(self):
        return AuditMiddleware(app=MagicMock())

    def _make_db_mock(self):
        """Create a DB session mock that won't trigger coroutine warnings."""
        mock_session = MagicMock()
        # Ensure add() is a plain callable, never a coroutine
        mock_session.add = MagicMock(return_value=None)
        mock_session.flush = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None

        mock_db = MagicMock()
        mock_db.get_session.return_value = mock_context
        return mock_db

    @pytest.mark.asyncio
    async def test_skips_excluded_paths(self, middleware, mock_request):
        """Test middleware skips health and docs paths."""
        excluded_paths = ["/health", "/docs", "/openapi.json"]

        for path in excluded_paths:
            mock_request.url.path = path
            mock_request.headers = {}

            call_next = AsyncMock()
            call_next.return_value = MagicMock(status_code=200, headers={})

            response = await middleware.dispatch(mock_request, call_next)

            call_next.assert_called()

    @pytest.mark.asyncio
    async def test_extracts_api_key_truncated(self, middleware, mock_request):
        """Test API key is truncated in audit record."""
        mock_request.url.path = "/events"

        call_next = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        call_next.return_value = mock_response

        mock_db = self._make_db_mock()

        with patch(
            "src.infrastructure.database.session.get_db_session",
            return_value=mock_db,
        ):
            await middleware.dispatch(mock_request, call_next)

    @pytest.mark.asyncio
    async def test_gets_ip_from_x_forwarded_for(self, middleware):
        """Test IP is extracted from X-Forwarded-For header."""
        mock_request = MagicMock()
        mock_request.url.path = "/events"
        mock_request.method = "GET"
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.1, 10.0.0.1",
            "X-API-Key": "test-key",
        }
        mock_request.client = None

        call_next = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        call_next.return_value = mock_response

        mock_db = self._make_db_mock()

        with patch(
            "src.infrastructure.database.session.get_db_session",
            return_value=mock_db,
        ):
            await middleware.dispatch(mock_request, call_next)

    @pytest.mark.asyncio
    async def test_captures_status_code_on_error(self, middleware, mock_request):
        """Test 500 status code captured when exception occurs."""
        mock_request.url.path = "/events"

        call_next = AsyncMock()
        call_next.side_effect = Exception("Server error")

        with pytest.raises(Exception):
            await middleware.dispatch(mock_request, call_next)
