import asyncio
import json
import re
from typing import AsyncGenerator

import httpx
from openai import APIConnectionError, APIError, APIStatusError, AsyncOpenAI, DefaultAsyncHttpxClient, RateLimitError

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
    provider = _resolve_provider()
    if provider == "openrouter":
        async for chunk in _stream_openrouter(system, user):
            yield chunk
        return
    if provider == "local":
        async for chunk in _stream_local_documentation(user):
            yield chunk
        return
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
    except APIError as exc:
        raise OpenAIUpstreamError(f"OpenAI API error: {_sanitize_error_text(str(exc))}") from exc

    yield "data: [DONE]\n\n"


async def get_quality_score(system: str, user: str) -> dict:
    provider = _resolve_provider()
    if provider == "openrouter":
        return await _get_openrouter_quality_score(system, user)
    if provider == "local":
        return _local_quality_score()
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


def _resolve_provider() -> str:
    provider = settings.llm_provider.lower()
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise OpenAIKeyMissingError("OpenRouter API key not configured")
        return "openrouter"
    if provider == "openai":
        return "openai"
    if provider == "local":
        return "local"
    if settings.openrouter_api_key:
        return "openrouter"
    if settings.openai_api_key:
        return "openai"
    return "local"


async def _stream_openrouter(system: str, user: str) -> AsyncGenerator[str, None]:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://venkat-023-documind-ai.hf.space",
        "X-Title": "DocuMind AI",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "max_tokens": settings.max_output_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as http:
            async with http.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    detail = await response.aread()
                    raise OpenAIUpstreamError(
                        f"OpenRouter API error {response.status_code}: "
                        f"{_sanitize_error_text(detail.decode('utf-8', errors='replace')[:500])}"
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        delta = event["choices"][0].get("delta", {}).get("content", "")
                    except Exception:
                        delta = ""
                    if delta:
                        escaped = delta.replace("\n", "\\n")
                        yield f"data: {escaped}\n\n"
    except OpenAIUpstreamError:
        raise
    except httpx.TimeoutException as exc:
        raise OpenAIUpstreamError("OpenRouter API request timed out before streaming started.") from exc
    except httpx.HTTPError as exc:
        raise OpenAIUpstreamError(f"OpenRouter API connection failed: {str(exc)}") from exc

    yield "data: [DONE]\n\n"


async def _get_openrouter_quality_score(system: str, user: str) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://venkat-023-documind-ai.hf.space",
        "X-Title": "DocuMind AI",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 700,
    }
    async with httpx.AsyncClient(timeout=45.0) as http:
        response = await http.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        return _local_quality_score()


async def _stream_local_documentation(user_prompt: str) -> AsyncGenerator[str, None]:
    code = _extract_code_from_prompt(user_prompt)
    language = _extract_code_language(user_prompt)
    docs = _build_local_documentation(code, language)
    for token in re.findall(r"\s+|[^\s]+", docs):
        escaped = token.replace("\n", "\\n")
        yield f"data: {escaped}\n\n"
        await asyncio.sleep(0)
    yield "data: [DONE]\n\n"


def _extract_code_from_prompt(user_prompt: str) -> str:
    match = re.search(r"```[^\n]*\n(?P<code>.*?)```", user_prompt, flags=re.S)
    return match.group("code").strip() if match else user_prompt[-4000:]


def _extract_code_language(user_prompt: str) -> str:
    match = re.search(r"```(?P<language>[^\n]*)\n", user_prompt)
    return (match.group("language").strip() or "text") if match else "text"


def _build_local_documentation(code: str, language: str) -> str:
    lines = code.splitlines()
    functions = re.findall(r"\b(?:def|function|fn)\s+([A-Za-z_][A-Za-z0-9_]*)", code)
    classes = re.findall(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", code)
    function_rows = "\n".join(
        f"| `{name}` | See source | Not inferred | Function detected in source. |"
        for name in functions[:30]
    ) or "| Not detected | - | - | No top-level functions were detected by the local fallback. |"

    return f"""# Generated Documentation

Documentation generated with DocuMind AI's local fallback mode because no external LLM provider is configured.

## Overview

This `{language}` source contains approximately {len(lines)} lines, {len(functions)} detected functions, and {len(classes)} detected classes.

## Detected Classes

{', '.join(f'`{name}`' for name in classes[:20]) if classes else 'No classes detected.'}

## API Reference

| Function | Parameters | Returns | Description |
|---|---|---|---|
{function_rows}

## Usage Notes

- Review the generated output before publishing.
- Configure `OPENROUTER_API_KEY` to use OpenRouter free models for richer AI-written documentation.
- Configure `OPENAI_API_KEY` only if the OpenAI project has active quota.
"""


def _local_quality_score() -> dict:
    return {
        "coverage": 65,
        "examples": 35,
        "params": 45,
        "edge_cases": 35,
        "overall": 50,
        "improvements": [
            "Configure OPENROUTER_API_KEY for free-model LLM output.",
            "Review parameter and return descriptions manually.",
            "Add examples for important functions.",
        ],
    }
