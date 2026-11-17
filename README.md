# Switchboard

An IT service desk agent that separates fast judgment from slow reasoning.

Most agents use one model for everything. Switchboard uses two, the way humans do: a fast, pattern-matching System 1 for decisions that don't need reasoning, and a slow, deliberate System 2 only where it earns its cost.

![Decision model flow](social/decision-models/out/decision-models-light.gif)

---

## The idea

**System 1 — [Jev](https://typesafe.ai) (TypeSafe)** answers questions like: *Is this a real IT request? Does this person have permission? Does this action need approval?* These are typed judgments — scoring against thresholds, routing to the right path — not open-ended reasoning. Jev runs in a single API call, returns structured JSON, and costs a fraction of a full LLM turn. It never writes prose.

**System 2 — Gemini** handles everything that actually needs thinking: understanding what the user wants, loading the right skill, calling tools, writing the reply. It runs only when System 1 has already decided that reasoning is warranted.

The result: guardrails and permission checks happen fast and cheaply every time. Gemini shows up only where it creates value.

---

## How a request moves through Switchboard

```
request
  └─ intake          identity resolution (fixed rule)
  └─ input_guardrail  Jev — 2 attack checks + 1 scope check (one call)
       ├─ block       injection or abuse → fixed decline
       ├─ hold        needs human review → specialist queue
       └─ proceed
            └─ understand_request  Jev — 8 intent questions (one call)
                 ├─ reply    → Quick reply: Gemini Lite writes a greeting or one clarifying question
                 ├─ handle   → Resolution agent: Gemini (Lite / Mid / Strong) loads a skill, calls tools, replies
                 └─ specialist → security matters go to a person
```

Jev runs twice per request — both times in a single API call each. Gemini runs at most once, with a model tier Jev selected based on the work ahead.

---

## Safety gate

Before any write tool executes, Jev runs a third check: *Is this person entitled to do this? Is someone trying to social-engineer the agent?* High-risk tools pause the run and send an approval request to a named approver (never the requester). The run resumes only on explicit sign-off; a timeout, a closed page, or no approver means the action does not run. The gate fails closed.

---

## Skills

Each skill is a markdown procedure (`skills/<name>/SKILL.md`) that tells Gemini what it can do, what tools it may use, and what sources to trust. The resolution agent loads exactly one skill per request. Skills ship with the codebase; they are the place to change procedures without touching Python.

| Skill | Covers |
|-------|--------|
| `account-access` | Password resets, MFA, account locks |
| `device-and-requests` | Hardware, software, procurement |
| `troubleshooting` | Connectivity, performance, app errors |
| `reply-style` | Voice and format applied to every Gemini response |

---

## Quick start

```bash
make install   # uv sync
make serve     # UI on http://127.0.0.1:5180
make test      # offline unit tests: thresholds, routing, permissions, tools, audit
```

Requires a `TYPESAFE_API_KEY` and GCP auth (`gcloud auth application-default login`). Copy `.env.example` to `.env` and fill in the values.

---

## Where each decision lives

| Decision | File |
|----------|------|
| Thresholds and routing | `nodes.py` |
| Question wording | `questions.py` |
| Tool permissions, model tiers, rate limits | `policy.toml` |
| Skill procedures | `skills/<name>/SKILL.md` |
| Reply voice and format | `skills/reply-style/SKILL.md` |
| Tool contracts and permission gate | `tools.py`, `harness.py` |
| Safety gate — production vs reversible, approval thresholds | `policy.toml [safety]`, `safety.py` |
| Approval flow | `approvals.py` |
| Audit trail (masked, append-only) | `audit.py` → `logs/audit.jsonl` |

---

## Stack

- **[Google ADK 2.x](https://adk.dev)** — `Workflow` graph, tool runner, streaming
- **[TypeSafe Jev](https://typesafe.ai)** — System 1 judgment model
- **Gemini** via Vertex AI — System 2 reasoning, three tiers (Lite / Mid / Strong)
- **FastAPI + SSE** — streaming server with per-event timestamps and TTFT
- **uv** — dependency management

---

## Author

Gaurav Lahoti · [github.com/gauravlahoti](https://github.com/gauravlahoti)

## License

MIT
