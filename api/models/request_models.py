from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class GitHubFetchRequest(BaseModel):
    url: str = Field(
        min_length=1,
        description="github.com/owner/repo/blob/branch/path or github.com/owner/repo/pull/N",
    )


class Symbol(BaseModel):
    name: str
    type: Literal["function", "class", "method"]
    line_start: int
    line_end: int
    params: List[str] = []
    return_type: Optional[str] = None
    is_async: bool = False
    docstring: Optional[str] = None


class ParsedSymbols(BaseModel):
    functions: List[Symbol]
    classes: List[Symbol]
    line_count: int
    language: str
    imports: List[str] = []


class GenerateRequest(BaseModel):
    code: str = Field(min_length=1)
    symbols: Optional[ParsedSymbols] = None
    format: Literal["readme", "jsdoc", "openapi", "confluence", "docusaurus"]
    onboarding_mode: bool = False
    self_critique: bool = True
    language: Optional[str] = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    source: str = ""
    report: str = ""
    source_label: str = ""
    history: List[ChatMessage] = []
