"""Integration tests for the real FastAPI routes."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from src.application.dto.event_dto import EventCreateDTO, EventResponseDTO
from src.application.services.event_service import EventService
from src.presentation.dependencies.auth import get_api_key, get_event_service
from src.presentation.routes.events import router as events_router
from src.presentation.routes.health import router as health_router


class StubEventService:
    """Lightweight service stub used to drive route behavior."""

    def __init__(self) -> None:
        self.rate_limited = False
        self.duplicate_id: str | None = None

    async def check_rate_limit(self, api_key: str) -> tuple[bool, int]:
        if self.rate_limited:
            return False, 101
        return True, 1

    async def check_idempotency(
        self, source: str, device_id: str, event_type: str
    ) -> tuple[bool, str | None]:
        if self.duplicate_id is not None:
            return True, self.duplicate_id
        return False, None

    async def create_event(
        self, dto: EventCreateDTO, background_tasks: BackgroundTasks
    ) -> EventResponseDTO:
        return EventResponseDTO(
            id=uuid4(),
            source=dto.source,
            customer_id=dto.customer_id,
            device_id=dto.device_id,
            event_type=dto.event_type,
            occurred_at=dto.occurred_at,
            metric_value=dto.metric_value,
            metadata=dto.metadata,
            severity="low",
            status="pending",
            created_at=datetime.now(UTC),
        )


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "source": "meraki",
        "customer_id": "cli-001",
        "device_id": "sw-44",
        "event_type": "device_down",
        "occurred_at": "2026-04-07T10:12:00Z",
        "metric_value": 0,
        "metadata": {"site": "Bogota"},
    }
    data.update(overrides)
    return data


@pytest.fixture
def stub_event_service() -> StubEventService:
    return StubEventService()


@pytest.fixture
def client(stub_event_service: StubEventService) -> TestClient:
    app = FastAPI()
    app.include_router(events_router)
    app.include_router(health_router)
    app.dependency_overrides[get_event_service] = lambda: stub_event_service
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_post_events_returns_202_for_valid_payload(client: TestClient) -> None:
    response = client.post("/events", json=_payload())
    assert response.status_code == 202
    body = response.json()
    assert body["source"] == "meraki"
    assert body["status"] == "pending"


def test_post_events_returns_422_for_invalid_payload(client: TestClient) -> None:
    payload = _payload()
    del payload["source"]
    response = client.post("/events", json=payload)
    assert response.status_code == 422


def test_post_events_returns_429_when_rate_limited(
    client: TestClient, stub_event_service: StubEventService
) -> None:
    stub_event_service.rate_limited = True
    response = client.post("/events", json=_payload(device_id="sw-45"))
    assert response.status_code == 429


def test_post_events_returns_409_for_duplicate(
    client: TestClient, stub_event_service: StubEventService
) -> None:
    stub_event_service.duplicate_id = "existing-id"
    response = client.post("/events", json=_payload(device_id="sw-46"))
    assert response.status_code == 409


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
