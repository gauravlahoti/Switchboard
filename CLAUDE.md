# desk, the Reflex IT service desk agent

ADK 2.x `Workflow` graph. Jev (TypeSafe System One, System 1) makes typed judgments. Code holds every rule.
Gemini (System 2) loads a skill, uses tools and writes the reply, only where reasoning is needed.

## Run locally

```
make install       # uv sync
make serve         # console on http://127.0.0.1:5180 (needs TYPESAFE_API_KEY and GCP auth)
make test          # offline unit tests: thresholds, routing, permissions, tools, audit
```

## Environment

`.env` holds local config. Never commit it. `.env.example` is the template.

| Var | Purpose |
|-----|---------|
| `TYPESAFE_API_KEY` | TypeSafe Jev key. Add to `.env`, never commit. Use Secret Manager when deployed |
| `GOOGLE_GENAI_USE_ENTERPRISE` | `true`, routes Gemini through Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex (`adk-deploy-trail`) |
| `GOOGLE_CLOUD_LOCATION` | `global` |

## Flow

```
request -> intake (identity) -> input guardrails -> understand request
  guardrails: proceed | hold -> specialist review | block (attack) | decline (not an IT matter, no model call)
  understand: reply      -> Quick reply: Gemini Lite writes a greeting or one clarifying question
              handle     -> Resolution agent: Gemini (tier Jev picks) loads a skill, uses tools, replies
              specialist -> security matters go to a person
```

| Node | Kind | File |
|------|------|------|
| intake | fixed rule, resolves who is asking | `nodes.py`, `identity.py` |
| input_guardrail | Jev, 2 attack checks and 1 scope check, one call | `agent.py`, `questions.py`, `nodes.py` |
| understand_request | Jev, 8 questions, one call | `agent.py`, `questions.py`, `nodes.py` |
| plan_work | Jev picks the model and tools from the permitted set | `agent.py`, `harness.py`, `questions.py` |
| reply_to_user (shown as Quick reply, a single model call) | Gemini Lite, always applies `skills/reply-style` | `agent.py`, `harness.py` |
| handle_request (shown as Resolution agent, an agent loop) | Gemini Lite, Mid or Strong plus skills and tools, always applies `skills/reply-style` | `agent.py`, `harness.py`, `tools.py` |
| hold_review, block_request (shown as Decline request), specialist_review | fixed text, personalised with the first name | `nodes.py` |

## Where each decision lives

| Decision | Where |
|----------|-------|
| Thresholds and routing order | `nodes.py` (constants and `understanding_path`) |
| Question wording | `questions.py` only |
| Who can use which tool, model tiers and prices, limits, the how-to read-only rule | `policy.toml` |
| Skill procedures and the tools each skill unlocks | `skills/<name>/SKILL.md` |
| Reply format and voice, applied to both Gemini steps | `skills/reply-style/SKILL.md` (always on, inlined, never offered to the model) |
| Tool contract, identity binding, permission gate | `tools.py`, `harness.py` |
| Which permitted tools help and which model tier suits the work | Jev (`select_questions` in `questions.py`), accepted by `harness.plan_from_selection` |
| Safety gate before a write tool: what each tool is (production, reversible) and the approval thresholds | `policy.toml` `[safety]`, table in `safety.py` |
| Pausing a run for a person's approval, fail closed | `approvals.py`, `POST /api/approve/{run_id}` |
| Who may approve which tool (profile ids, never the requester) | `policy.toml` `[safety.approvers]`, `identity.approvers_for` |
| Streaming, time to first token, event timestamps | `server.py` (`token`, `ttft`, every event carries `t` in ms) |
| Audit trail (masked, append-only) | `audit.py` writes `logs/audit.jsonl` |

## Key rules

- **Never hand-edit** `pyproject.toml [tool.agents-cli]` or `App(name="app")`.
- **ADK 2.14 routing:** use a RoutingMap dict `(source, {"route": target})`.
- **A failed Jev or LLM call surfaces as an error**, never a silent "no".
- **A tool the person cannot use does not exist for the model.** It is absent from the schema, rejected by the gate, and the plan lists it as hidden with a reason.
- **Targets that must be the requester are bound in code**, never model parameters. Ticket priority and category come from the triage.
- **Reuse one `Gemini` object per tier** (`harness._model`). A new agent per request pays about 6 s to authenticate.
- **Model IDs** come from `gcloud ai model-garden models list --project=adk-deploy-trail --billing-project=adk-deploy-trail`, CAN_PREDICT = Yes. Prices live in `policy.toml` (date and prompt-size aware, read from the Gemini API pricing page on 2026-11-17, confirm against Vertex billing).
- **Jev judges, code decides, and code answers what code knows.** Whether a tool touches production or can be undone is a policy fact, not a Jev question. Jev judges privilege, verification and social engineering for the safety gate.
- **The safety gate fails closed.** A failed safety call, no approver, no answer in `approval_seconds` or a closed page all mean the action does not run. Time spent waiting for a person is added back to the agent timeout.
- **Approval is by a named approver, checked on the server.** `/api/approve` needs `by` (a profile id) and returns 403 unless it is on the list for that tool and is not the requester. John Reyes (`manager`) is the approver. The page switches to John to answer and back to the requester after. Today `by` is sent by the page, so a deployed version must take it from the SSO session.
- **Sign-in is a stand-in.** `policy.toml` profiles replace SSO claims. A deployed version must take identity from the platform, never from the request body.
- **Synthetic data resets on every server start** (`store.reset`). `POST /api/demo/reset` does the same.
- Never log or print raw PII. `audit.mask` hides emails and long numbers, and the audit trail holds ids and decisions, not message text.

## Not built yet

A real specialist queue and an approver taken from SSO instead of the page's `by` field, `query_logs`, real SSO,
Cloud Run deploy, a fallback tier when the Strong model returns 429.
