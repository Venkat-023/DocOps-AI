from fastapi import APIRouter

from api.config import settings
from api.models.response_models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return {
        "status": "ok",
        "model": settings.openai_model,
        "github_configured": bool(settings.github_token),
    }
