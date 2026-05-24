from typing import Any, Dict

from pydantic import BaseModel


class GitHubFetchResponse(BaseModel):
    content: str
    file_path: str
    language: str
    is_pr: bool
    symbols: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    model: str
    llm_provider: str
    github_configured: bool
