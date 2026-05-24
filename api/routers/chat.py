from fastapi import APIRouter, HTTPException

from api.models.request_models import ChatRequest
from api.services.chat_service import answer_question

router = APIRouter()


@router.post("")
async def chat(req: ChatRequest):
    try:
        return await answer_question(
            question=req.question,
            source=req.source,
            report=req.report,
            source_label=req.source_label,
            history=req.history,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat failed: {type(exc).__name__}") from exc
