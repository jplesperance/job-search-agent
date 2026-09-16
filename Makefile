.PHONY: test lint run

test:
	pytest

lint:
	ruff check src tests

run:
	uvicorn job_agent.api.main:app --reload --app-dir src
