.PHONY: dev api dashboard migrate seed test lint clean full

dev:
	@echo "Starting full development stack..."
	@python -m uvicorn apps.api.main:app --reload --port 8000

full:
	python scripts/run_observatory.py

api:
	python -m uvicorn apps.api.main:app --reload --port 8000

dashboard:
	cd apps/dashboard && npm run dev

migrate:
	alembic upgrade head

seed:
	python -m database.seeds.seed_all

test:
	pytest tests/ -v

lint:
	ruff check .
	ruff format --check .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
