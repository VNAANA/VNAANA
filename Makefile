.PHONY: quality quality-python quality-frontend quality-architecture quality-duplication \
        format format-python format-frontend

# Run all static quality gates. Test execution remains in the existing test job.
quality: quality-python quality-frontend quality-architecture quality-duplication

quality-python:
	python -m ruff check Backend
	python -m ruff format --check Backend

quality-frontend:
	npm --prefix Frontend run lint
	npm --prefix Frontend run typecheck
	npm --prefix Frontend run format:check

quality-architecture:
	lint-imports

quality-duplication:
	npm --prefix Frontend run duplication

# Formatting commands are opt-in local fixes; CI only runs check commands.
format: format-python format-frontend

format-python:
	python -m ruff check --fix Backend
	python -m ruff format Backend

format-frontend:
	npm --prefix Frontend run format
