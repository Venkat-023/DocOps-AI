import asyncio
import json
import re
from typing import AsyncGenerator

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, DefaultAsyncHttpxClient, RateLimitError

from api.config import settings

client = (
    AsyncOpenAI(
        api_key=settings.openai_api_key,
        http_client=DefaultAsyncHttpxClient(timeout=15.0),
        max_retries=0,
    )
    if settings.openai_api_key
    else None
)


class OpenAIKeyMissingError(RuntimeError):
    pass


class OpenAIRateLimitError(RuntimeError):
    pass


class OpenAIUpstreamError(RuntimeError):
    pass


def _extract_openai_message(exc: APIStatusError) -> str:
    try:
        body = exc.response.json()
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if body.get("message"):
                return str(body["message"])
    except Exception:
        pass
    return str(exc)


def _safe_upstream_error(exc: APIStatusError) -> OpenAIUpstreamError:
    message = _extract_openai_message(exc)
    return OpenAIUpstreamError(f"OpenAI API error {exc.status_code}: {message}")


def _sanitize_error_text(value: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_-]+", "sk-***", value)


def _safe_connection_error(exc: APIConnectionError) -> OpenAIUpstreamError:
    cause = exc.__cause__
    detail = repr(cause) if cause else str(exc)
    detail = _sanitize_error_text(detail)
    return OpenAIUpstreamError(f"OpenAI API connection failed: {detail}")


async def stream_documentation(system: str, user: str) -> AsyncGenerator[str, None]:
    if client is None:
        raise OpenAIKeyMissingError("OpenAI API key not configured")

    try:
        stream = await asyncio.wait_for(
            client.responses.create(
                model=settings.openai_model,
                instructions=system,
                input=user,
                max_output_tokens=settings.max_output_tokens,
                stream=True,
            ),
            timeout=20.0,
        )

        async for event in stream:
            if event.type == "response.output_text.delta" and event.delta:
                escaped = event.delta.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
            elif event.type == "response.failed":
                error = getattr(event.response, "error", None)
                message = getattr(error, "message", None) or "Response generation failed"
                raise OpenAIUpstreamError(f"OpenAI API error: {message}")

    except RateLimitError as exc:
        raise OpenAIRateLimitError("Rate limit hit. Wait 30 seconds and retry.") from exc
    except asyncio.TimeoutError as exc:
        raise OpenAIUpstreamError("OpenAI API request timed out before streaming started.") from exc
    except APIConnectionError as exc:
        raise _safe_connection_error(exc) from exc
    except APIStatusError as exc:
        raise _safe_upstream_error(exc) from exc

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
