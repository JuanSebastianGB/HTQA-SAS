"""Notification service for sending alerts."""

from src.domain.ports.repository import NotificationServicePort


class NotificationService:
    """Service for sending notifications."""

    def __init__(
        self,
        notification_port: NotificationServicePort,
        *,
        recipient_email: str,
    ):
        self._port = notification_port
        self._recipient_email = recipient_email

    async def notify_critical_event(self, event_id: str, device_id: str, message: str) -> None:
        """Send notification for critical events."""
        subject = f"Critical Event Alert: {event_id}"
        body = f"Device: {device_id}\nMessage: {message}"
        await self._port.send(self._recipient_email, subject, body)
