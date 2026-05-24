from fastapi import APIRouter, HTTPException

from api.config import settings
from api.models.request_models import GitHubFetchRequest
from api.models.response_models import GitHubFetchResponse
from api.services.github_service import (
    GitHubRateLimitError,
    GitHubUnavailableError,
    fetch_github_content,
)
from api.services.parser_service import extract_symbols

router = APIRouter()


@router.post("", response_model=GitHubFetchResponse)
async def fetch_github(req: GitHubFetchRequest):
    try:
        result = await fetch_github_content(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubRateLimitError as exc:
        raise HTTPException(status_code=429, detail="Rate limit hit. Wait 30 seconds and retry.") from exc
    except GitHubUnavailableError as exc:
        raise HTTPException(
            status_code=502, detail="Could not reach GitHub. Check the URL and try again."
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Could not reach GitHub. Check the URL and try again."
        ) from exc

    line_count = len(result["content"].splitlines())
    if line_count > settings.max_file_size_lines:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large ({line_count} lines). "
                f"Maximum is {settings.max_file_size_lines} lines."
            ),
        )

    symbols = extract_symbols(result["content"], result["language"])
    return {
        "content": result["content"],
        "file_path": result["file_path"],
        "language": result["language"],
        "is_pr": result["is_pr"],
        "symbols": symbols.model_dump(),
    }
