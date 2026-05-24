from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        alias="ALLOWED_ORIGINS",
    )
    max_file_size_lines: int = Field(default=800, alias="MAX_FILE_SIZE_LINES")
    openai_model: str = Field(default="gpt-5.2", alias="OPENAI_MODEL")
    max_output_tokens: int = Field(default=4000, alias="MAX_OUTPUT_TOKENS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("openai_api_key", "github_token", "openai_model", mode="before")
    @classmethod
    def strip_secret_values(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
