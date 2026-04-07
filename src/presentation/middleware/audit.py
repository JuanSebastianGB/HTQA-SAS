"""Audit middleware for capturing request metadata."""

import logging
import time
from datetime import UTC, datetime
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.infrastructure.database.models import AuditLogModel

logger = logging.getLogger(__name__)

# Headers that contain sensitive data to sanitize
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "cookie",
    "set-cookie",
}


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Sanitize sensitive headers by redacting their values.

    Args:
        headers: Raw request headers

    Returns:
        Headers with sensitive values redacted
    """
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            # Redact sensitive headers - show only first 4 chars for identification
            if value:
                sanitized[key] = value[:4] + "***REDACTED***"
            else:
                sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value
    return sanitized


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for capturing and storing audit information.

    Captures: timestamp, api_key, method, path, status_code, ip_address.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and capture audit metadata."""
        # Skip audit for health and OpenAPI endpoints
        excluded_paths = {
            "/health",
            "/docs",
            "/docs/",
            "/redoc",
            "/redoc/",
            "/openapi.json",
        }
        if request.url.path in excluded_paths:
            return await call_next(request)

        # Capture request start time
        start_time = time.time()

        # Extract request metadata
        method = request.method
        path = request.url.path

        # Get API key (sanitize it)
        api_key_header = request.headers.get("X-API-Key")
        api_key = None
        if api_key_header:
            # Store only a truncated version for audit
            api_key = api_key_header[:8] + "***" if len(api_key_header) > 8 else "***"

        # Get client IP address
        ip_address = request.headers.get("X-Forwarded-For")
        if not ip_address:
            ip_address = request.client.host if request.client else None

        # Sanitize and only log headers in debug mode to avoid leaking secrets.
        if logger.isEnabledFor(logging.DEBUG):
            sanitized_headers = sanitize_headers(dict(request.headers))
            logger.debug("Request headers: %s", sanitized_headers)

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Capture 500 errors
            status_code = 500
            logger.error(f"Request failed: {e}")
            raise
        finally:
            # Calculate processing time
            process_time = time.time() - start_time

        # Save audit record asynchronously (don't block response)
        try:
            await self._save_audit_record(
                timestamp=datetime.now(UTC),
                api_key=api_key,
                method=method,
                path=path,
                status_code=status_code,
                ip_address=ip_address,
            )
        except Exception as e:
            # Log but don't fail the request if audit fails
            logger.warning(f"Failed to save audit record: {e}")

        # Add processing time header
        response.headers["X-Process-Time"] = str(process_time)

        return response

    async def _save_audit_record(
        self,
        timestamp: datetime,
        api_key: str | None,
        method: str,
        path: str,
        status_code: int,
        ip_address: str | None,
    ) -> None:
        """Save audit record to database.

        Uses the global database session to persist the record.
        """
        from src.infrastructure.database.session import get_db_session

        db_session = get_db_session()

        # Create audit log model
        audit_record = AuditLogModel(
            timestamp=timestamp,
            api_key=api_key,
            method=method,
            path=path,
            status_code=status_code,
            ip_address=ip_address,
        )

        # Save to database
        async with db_session.get_session() as session:
            session.add(audit_record)
            await session.flush()
