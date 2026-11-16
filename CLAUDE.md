# desk — IT Service Desk Triage Agent

ADK 2.0 `Workflow` graph. Jev (TypeSafe System One) makes typed judgments.
Code holds all rules. LLMs reason and write.

## Run locally

```
make install       # uv sync
make run           # fixture mode, no keys needed
make run-live      # live Jev + LLM (needs TYPESAFE_API_KEY and GCP auth)
make test          # unit tests for truth tables
make playground    # interactive web UI
```

## Environment

`.env` holds local config. Never commit it. `.env.example` is the template.

| Var | Purpose |
|-----|---------|
| `TYPESAFE_API_KEY` | TypeSafe Jev key — add to `.env`, do not commit |
| `JEV_FIXTURE_MODE` | `1` = load fixture JSONs (default); `0` = live Jev calls |
| `GOOGLE_GENAI_USE_ENTERPRISE` | `true` — routes Gemini through Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex (`adk-deploy-trail`) |
| `GOOGLE_CLOUD_LOCATION` | `global` |

## Architecture

```
START -> intake -> jev_triage -> policy_router
  -> security -> escalate -> prep_reply -> reply_llm
  -> action   -> tier_llm_node -> execute_tool -> prep_reply -> reply_llm
  -> clarify  -> clarify_llm -> prep_reply -> reply_llm
```

| Node | Kind | File |
|------|------|------|
| intake | deterministic | nodes.py |
| jev_triage | Jev (async) | agent.py + jev.py |
| policy_router | deterministic | nodes.py |
| escalate | deterministic | nodes.py |
| tier_llm_node | LLM (dynamic model) | agent.py |
| clarify_llm | LLM | agent.py |
| execute_tool | deterministic | nodes.py |
| prep_reply | deterministic | nodes.py |
| reply_llm | LLM | agent.py |

## Key rules

- **Never hand-edit** `pyproject.toml [tool.agents-cli]` or `App(name="app")`.
- **ADK 2.14 routing:** use RoutingMap dict `(source, {"route": target})` — 3-tuples fail.
- **Jev question wording** lives exclusively in `app/questions.py`.
- **A failed Jev or LLM call surfaces as an error**, never a silent "no".
- **TYPESAFE_API_KEY** stays in `.env` and Secret Manager, never in code or git.
- **Risky tools** (`restart_service`, `grant_access`) raise immediately until sprint 2.
- **LLM tier IDs** are placeholders. Resolve with gcloud before first live run:

```
gcloud ai model-garden models list --project=adk-deploy-trail | grep -i gemini
# Check CAN_PREDICT column is Yes
```

## Sprint plan

| Sprint | Goal | Status |
|--------|------|--------|
| 1 | Screen and route: real Jev, real LLM, real tools on synthetic data | active |
| 2 | Safety gate: jev_safety, safety_gate truth table, approval HITL | — |
| 3 | Production UI: graph pane, chat pane, trace events | — |
| 4 | Recording, voice, Cloud Run deploy | — |
| 5 | Portfolio wiring | — |

---

## Agents-CLI operational notes

- **Model 404 errors**: fix `GOOGLE_CLOUD_LOCATION` (e.g., `global`), not the model name.
- **Never verify model IDs from docs or memory** — always run the gcloud command above first.
- **Run Python with `uv`**: `uv run python script.py`
- **Stop on repeated errors**: if the same error appears 3+ times, fix the root cause.
