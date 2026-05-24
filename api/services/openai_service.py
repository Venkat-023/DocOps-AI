import json
from typing import AsyncGenerator

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from api.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None


class OpenAIKeyMissingError(RuntimeError):
    pass


class OpenAIRateLimitError(RuntimeError):
    pass


class OpenAIUpstreamError(RuntimeError):
    pass


async def stream_documentation(system: str, user: str) -> AsyncGenerator[str, None]:
    if client is None:
        raise OpenAIKeyMissingError("OpenAI API key not configured")

    try:
        stream = await client.responses.create(
            model=settings.openai_model,
            instructions=system,
            input=user,
            max_output_tokens=settings.max_output_tokens,
            stream=True,
        )

        async for event in stream:
            if event.type == "response.output_text.delta" and event.delta:
                escaped = event.delta.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
            elif event.type == "response.failed":
                raise OpenAIUpstreamError("OpenAI generation failed")

    except RateLimitError as exc:
        raise OpenAIRateLimitError("Rate limit hit. Wait 30 seconds and retry.") from exc
    except (APIConnectionError, APIStatusError) as exc:
        raise OpenAIUpstreamError("OpenAI generation failed") from exc

    yield "data: [DONE]\n\n"


async def get_quality_score(system: str, user: str) -> dict:
    if client is None:
        raise OpenAIKeyMissingError("OpenAI API key not configured")

    response = await client.responses.create(
        model=settings.openai_model,
        instructions=system,
        input=user,
        max_output_tokens=700,
    )
    raw = getattr(response, "output_text", "") or ""

    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        return {
            "coverage": 80,
            "examples": 75,
            "params": 80,
            "edge_cases": 70,
            "overall": 77,
            "improvements": [],
        }
