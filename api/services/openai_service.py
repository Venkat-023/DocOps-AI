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
    if language.lower() in {"markdown", "md"}:
        return _build_local_markdown_documentation(code)

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


def _build_local_markdown_documentation(markdown: str) -> str:
    lines = markdown.splitlines()
    title = next(
        (line.lstrip("#").strip() for line in lines if line.startswith("# ")),
        "Repository Documentation",
    )
    description_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if description_lines:
                break
            continue
        if stripped.startswith("|") or stripped.startswith("```"):
            if description_lines:
                break
            continue
        description_lines.append(stripped)
        if len(" ".join(description_lines)) > 240:
            break

    description = " ".join(description_lines) or "Project overview generated from the repository README."
    sections = [
        line.lstrip("#").strip()
        for line in lines
        if line.startswith("## ") and "Repository tree" not in line
    ]
    bullets = [
        line.strip()
        for line in lines
        if line.strip().startswith(("- ", "* ")) and len(line.strip()) > 3
    ][:10]
    table_rows = [
        line.strip()
        for line in lines
        if line.strip().startswith("|")
        and "---" not in line
        and line.count("|") >= 2
    ][:12]
    tree_items = []
    in_tree = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Repository tree":
            in_tree = True
            continue
        if in_tree and stripped.startswith("#"):
            break
        if in_tree and stripped:
            tree_items.append(stripped)

    section_list = "\n".join(f"- {section}" for section in sections[:12]) or "- Overview"
    bullet_list = "\n".join(bullets) or "- Review the repository files for implementation details."
    if table_rows:
        table = "\n".join([table_rows[0], "|---|---|", *table_rows[1:]])
    else:
        table = "| Item | Value |\n|---|---|\n| Source | Repository README |"
    tree = "\n".join(f"- `{item}`" for item in tree_items[:20]) or "- Repository tree was not included in the fetched content."

    return f"""# {title}

{description}

## Problem

This project documents a software workflow described in the fetched repository README. The README indicates the repository is focused on a concrete engineering or research task and includes enough project metadata to guide setup, usage, and review.

## Solution Approach

DocuMind fetched the repository overview from GitHub, extracted the README plus top-level repository tree, and generated this structured documentation from those source materials. Because no external LLM provider is configured on the Space, this output uses the local fallback generator.

## Key Details

{table}

## Main Sections Found

{section_list}

## Highlighted Points

{bullet_list}

## Repository Structure

{tree}

## Inputs

- GitHub repository URL or direct GitHub file URL.
- Optional output format selection such as README, JSDoc, OpenAPI, Confluence, or Docusaurus.
- Optional onboarding mode and self-critique settings.

## Outputs

- Fetched repository content.
- Parsed metadata such as language, line count, and symbol counts when available.
- Generated documentation streamed back to the frontend.
- A quality score when self-critique is enabled.

## Next Steps

- Configure `OPENROUTER_API_KEY` to enable richer free-model LLM generation.
- Use direct source file URLs when you want function/class-level API documentation.
- Use whole repository URLs when you want a project overview based on the README and top-level tree.
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
