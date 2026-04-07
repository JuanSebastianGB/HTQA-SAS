"""Mock email notifier implementation (logging only)."""

import logging

from src.domain.ports.repository import NotificationServicePort

logger = logging.getLogger(__name__)


class MockEmailNotifier(NotificationServicePort):
    """Mock email notifier that logs notifications."""

    async def send(self, recipient: str, subject: str, body: str) -> None:
        """Send notification by logging (mock implementation)."""
        logger.info(f"EMAIL NOTIFICATION\nTo: {recipient}\nSubject: {subject}\nBody: {body}")
