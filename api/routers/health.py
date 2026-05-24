from fastapi import APIRouter

from api.config import settings
from api.models.response_models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    provider = settings.llm_provider.lower()
    if provider == "auto":
        provider = "openrouter" if settings.openrouter_api_key else "openai" if settings.openai_api_key else "local"
    model = (
        settings.openrouter_model
        if provider == "openrouter"
        else settings.openai_model
        if provider == "openai"
        else "local-fallback"
    )
    return {
        "status": "ok",
        "model": model,
        "llm_provider": provider,
        "github_configured": bool(settings.github_token),
    }
