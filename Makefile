.PHONY: install run run-live test eval seed playground

install:
	uv sync

run:
	JEV_FIXTURE_MODE=1 uv run agents-cli run "I forgot my password and I am locked out before a client call."

run-live:
	JEV_FIXTURE_MODE=0 uv run agents-cli run "I forgot my password and I am locked out before a client call."

test:
	uv run python -m pytest tests/unit/ -v

eval:
	uv run agents-cli eval run

seed:
	uv run python -c "from app.store import store; print('Store seeded:', store._path)"

playground:
	JEV_FIXTURE_MODE=1 uv run agents-cli playground
