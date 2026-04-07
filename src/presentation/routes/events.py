"""Events API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from src.application.dto.event_dto import EventCreateDTO, EventResponseDTO
from src.application.exceptions import RedisUnavailableError
from src.application.services.event_service import EventService
from src.presentation.dependencies.auth import get_api_key, get_event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "",
    response_model=EventResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Event accepted for asynchronous processing"},
        401: {"description": "Invalid or missing API key"},
        409: {"description": "Duplicate event within 5-minute idempotency window"},
        422: {"description": "Validation error — missing or invalid fields"},
        429: {"description": "Rate limit exceeded for API key"},
        503: {"description": "Redis/cache unavailable after retries"},
    },
)
async def create_event(
    event_dto: EventCreateDTO,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    event_service: EventService = Depends(get_event_service),
) -> EventResponseDTO:
    """Receive, validate, and queue an event for asynchronous processing.

    Flow:
    1. Rate limit check (fixed-window counter in Redis: INCR + EXPIRE per window)
    2. Idempotency check (5-minute window via Redis SETNX)
    3. Severity classification
    4. Persist event to database (status: PENDING)
    5. Return 202 Accepted immediately
    6. If severity is CRITICAL, schedule background notification
    """
    try:
        # 1. Rate limiting
        is_allowed, _ = await event_service.check_rate_limit(api_key)
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
            )

        # 2. Idempotency check
        is_duplicate, existing_id = await event_service.check_idempotency(
            event_dto.source, event_dto.device_id, event_dto.event_type
        )
        if is_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate event detected. Existing event: {existing_id}",
            )

        # 3-6. Create event (severity classification, persist, background task)
        return await event_service.create_event(event_dto, background_tasks)
    except RedisUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service temporarily unavailable. Retry later.",
        ) from None
