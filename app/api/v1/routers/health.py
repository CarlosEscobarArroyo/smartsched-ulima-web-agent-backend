from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from app.core.config import get_settings

    settings = get_settings()
    return HealthResponse(status="ok", environment=settings.environment)
