import os
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient

JEV_MODEL = "jev-latest"
# USD per million input tokens; output tokens are free (docs.typesafe.ai/go/models)
JEV_PRICE_PER_MTOK_IN = 0.042


def _dump(question: Any) -> Any:
    return question.model_dump(mode="json", exclude_none=True) if hasattr(question, "model_dump") else repr(question)


async def ask_jev(
    bundle: str, questions: dict, state: dict
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Call Jev for a named bundle of questions. A failed call always raises."""
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY is not set. Add it to .env.")

    async with AsyncTypeSafeClient(api_key=api_key) as client:
        response = await client.system_one(
            model=JEV_MODEL,
            state=state,
            questions=questions,
        )
        tokens = response.usage.input_tokens or 0
        usage = {
            "calls": 1,
            "input_tokens": tokens,
            "cost_usd": tokens * JEV_PRICE_PER_MTOK_IN / 1_000_000,
        }
        raw = {
            "model": response.model,
            "request_id": response.request_id,
            "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
            "answers": {name: answer.model_dump(mode="json") for name, answer in response.answers.items()},
            "request": {
                "model": JEV_MODEL,
                "state": state,
                "questions": {name: _dump(q) for name, q in questions.items()},
            },
        }
        return dict(response.answers), usage, raw
