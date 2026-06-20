.PHONY: run lint format test clean

run:
	PYTHONUNBUFFERED=1 uvicorn backend.src.app:app --reload --port 5000
lint:
	ruff check .

format:
	ruff format .

check: format lint
