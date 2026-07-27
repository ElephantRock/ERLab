.PHONY: test test-all lint format format-check check bench clean db-migrate

test:
	python -m pytest -m "not slow" --cov=backend --cov-report=term-missing

test-all:
	python -m pytest --cov=backend --cov-report=term-missing

lint:
	ruff check backend/

format:
	ruff format backend/

format-check:
	ruff format --check backend/

check: lint format-check test

bench:
	python -m pytest -m slow backend/tests/test_benchmarks/ --benchmark-only

db-migrate:
	python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage .benchmarks/
