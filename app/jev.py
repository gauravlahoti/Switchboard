import json
import os
from pathlib import Path
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, ChoiceAnswer, NoulAnswer, ScoreAnswer

JEV_MODEL = "jev-latest"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "jev"


def _fixture_mode() -> bool:
    return os.environ.get("JEV_FIXTURE_MODE", "1") == "1"


def _reconstruct_answers(raw: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, data in raw.items():
        t = data.get("type")
        if t == "noul":
            result[name] = NoulAnswer(**data)
        elif t == "choice":
            result[name] = ChoiceAnswer(**data)
        elif t == "score":
            safe = dict(data)
            if "legend" in safe:
                safe["legend"] = {int(k): v for k, v in safe["legend"].items()}
            if "probabilities" in safe:
                safe["probabilities"] = {int(k): float(v) for k, v in safe["probabilities"].items()}
            result[name] = ScoreAnswer(**safe)
        else:
            result[name] = data
    return result


def _load_fixture(bundle: str) -> dict[str, Any]:
    path = FIXTURE_DIR / f"{bundle}.json"
    if not path.exists():
        raise RuntimeError(
            f"Jev fixture not found: {path}. "
            "Either add the fixture or set JEV_FIXTURE_MODE=0 for live calls."
        )
    with open(path, encoding="utf-8") as fh:
        return _reconstruct_answers(json.load(fh))


async def ask_jev(bundle: str, questions: dict, state: dict) -> dict[str, Any]:
    """Call Jev for a named bundle of questions.

    bundle: fixture filename stem ('triage', 'safety')
    A failed call always raises — never returns a silent default.
    """
    if _fixture_mode():
        return _load_fixture(bundle)

    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY is not set. Add it to .env.")

    async with AsyncTypeSafeClient(api_key=api_key) as client:
        response = await client.system_one(
            model=JEV_MODEL,
            state=state,
            questions=questions,
        )
        return dict(response.answers)
