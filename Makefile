PYTHON ?= python3.12
VENV ?= .venv
PIP := $(VENV)/bin/pip
VENV_PYTHON := $(VENV)/bin/python
PYTEST := $(VENV_PYTHON) -m pytest
RUFF := $(VENV_PYTHON) -m ruff
MYPY := $(VENV_PYTHON) -m mypy
PIP_AUDIT := $(VENV_PYTHON) -m pip_audit

.PHONY: setup setup-backend setup-frontend dev backend-dev frontend-dev migrate seed reset-demo validate-public-data warmup acceptance final-acceptance backup-demo restore-demo test test-backend test-frontend test-e2e lint typecheck build check security-audit up down clean

setup: setup-backend setup-frontend

setup-backend:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e "./backend[dev]"

setup-frontend:
	npm install

dev:
	@echo "Run 'make backend-dev' and 'make frontend-dev' in two terminals, or use 'make up' for one-command startup."

backend-dev:
	cd backend && ../$(VENV_PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	npm --workspace frontend run dev -- --host 0.0.0.0

migrate:
	cd backend && ../$(VENV_PYTHON) -m alembic upgrade head

seed: migrate
	cd backend && ../$(VENV)/bin/python -m app.cli seed

reset-demo: migrate
	cd backend && ../$(VENV)/bin/python -m app.cli seed --reset

validate-public-data:
	cd backend && ../$(VENV)/bin/python -m app.cli validate-public-data

warmup:
	$(PYTHON) scripts/demo_warmup.py --api-url "$${API_URL:-http://127.0.0.1:8000}"

acceptance:
	$(PYTHON) scripts/acceptance_check.py --api-url "$${API_URL:-http://127.0.0.1:8000}" --web-url "$${WEB_URL:-http://127.0.0.1:8080}"

final-acceptance:
	$(PYTHON) scripts/final_delivery_check.py --api-url "$${API_URL:-http://127.0.0.1:8000}" --web-url "$${WEB_URL:-http://127.0.0.1:8080}"

backup-demo:
	test -n "$(OUTPUT)" || (echo "Usage: make backup-demo OUTPUT=/absolute/path/wealthtwin.sqlite" && exit 2)
	cd backend && ../$(VENV)/bin/python -m app.cli backup-demo --output "$(OUTPUT)"

restore-demo:
	test -n "$(INPUT)" || (echo "Usage: make restore-demo INPUT=/absolute/path/wealthtwin.sqlite" && exit 2)
	cd backend && ../$(VENV)/bin/python -m app.cli restore-demo --input "$(INPUT)" --confirm restore_synthetic_demo

test: test-backend test-frontend

test-backend:
	cd backend && ../$(PYTEST) -q

test-frontend:
	npm --workspace frontend run test

test-e2e:
	npm --workspace frontend run test:e2e

lint:
	cd backend && ../$(RUFF) check app tests alembic
	npm --workspace frontend run lint

typecheck:
	cd backend && ../$(MYPY) app
	npm --workspace frontend run typecheck

build:
	npm --workspace frontend run build

check: lint typecheck test build

# Dependency intelligence requires registry/network access; the application and
# normal offline check remain independent of this explicit supply-chain gate.
security-audit:
	$(PIP_AUDIT) --local
	npm audit --omit=dev --audit-level=high

up:
	docker compose up --build

down:
	docker compose down

clean:
	find backend -type d -name __pycache__ -prune -exec rm -r {} +
	rm -rf frontend/dist frontend/playwright-report frontend/test-results
