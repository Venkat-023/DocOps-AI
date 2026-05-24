from api.models.request_models import ParsedSymbols
from api.services.openai_service import get_quality_score
from api.services.prompt_service import CRITIQUE_SYSTEM, build_critique_prompt


async def score_documentation(code: str, documentation: str, symbols: ParsedSymbols | None) -> dict:
    return await get_quality_score(CRITIQUE_SYSTEM, build_critique_prompt(code, documentation, symbols))
