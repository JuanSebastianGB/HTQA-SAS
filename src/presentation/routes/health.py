"""Health check API route."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="", tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={"status": "healthy", "service": "htqa-events"},
        status_code=status.HTTP_200_OK,
    )
