import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.config import settings
from api.models.request_models import GenerateRequest
from api.services.openai_service import (
    OpenAIKeyMissingError,
    OpenAIRateLimitError,
    OpenAIUpstreamError,
    stream_documentation,
)
from api.services.prompt_service import build_prompt
from api.services.quality_service import score_documentation

router = APIRouter()


@router.post("")
async def generate_docs(req: GenerateRequest):
    if not settings.openai_api_key:
        raise HTTPException(status_code=401, detail="OpenAI API key not configured")

    line_count = len(req.code.splitlines())
    if line_count > settings.max_file_size_lines:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large ({line_count} lines). "
                f"Maximum is {settings.max_file_size_lines} lines."
            ),
        )

    system, user = build_prompt(req)

    async def event_generator():
        full_output = []
        token_count = 0

        try:
            async for chunk in stream_documentation(system, user):
                if chunk.startswith("data: [DONE]"):
                    break

                token = chunk.removeprefix("data: ").removesuffix("\n\n").replace("\\n", "\n")
                full_output.append(token)
                token_count += 1
                yield chunk

            full_text = "".join(full_output)
            yield f"data: [TOKENS]{token_count}\n\n"

            if req.self_critique:
                try:
                    score = await score_documentation(req.code, full_text, req.symbols)
                    yield f"data: [SCORE]{json.dumps(score)}\n\n"
                except Exception:
                    pass

            yield "data: [DONE]\n\n"
        except OpenAIRateLimitError:
            yield "data: [ERROR]Rate limit hit. Wait 30 seconds and retry.\n\n"
            yield "data: [DONE]\n\n"
        except OpenAIKeyMissingError as exc:
            yield f"data: [ERROR]{str(exc)}\n\n"
            yield "data: [DONE]\n\n"
        except OpenAIUpstreamError as exc:
            yield f"data: [ERROR]{str(exc)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
