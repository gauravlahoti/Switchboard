.PHONY: install serve test eval playground

install:
	uv sync

serve:
	uv run uvicorn server:server --port 5180

test:
	uv run python -m pytest tests/unit/ -v

eval:
	uv run agents-cli eval run

playground:
	uv run agents-cli playground
