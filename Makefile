.PHONY: test lint run validate-kb seed-kb seed-kb-dry-run search-evidence verify-phase2

test:
	pytest

lint:
	ruff check src tests

run:
	uvicorn job_agent.api.main:app --reload --app-dir src

validate-kb:
	PYTHONPATH=src python scripts/validate_knowledge_base.py

seed-kb:
	PYTHONPATH=src python scripts/import_knowledge_base.py

seed-kb-dry-run:
	PYTHONPATH=src python scripts/import_knowledge_base.py --dry-run

search-evidence:
	PYTHONPATH=src python scripts/search_evidence.py --skill "Application Security" --limit 10

verify-phase2:
	PYTHONPATH=src python scripts/verify_phase2.py
