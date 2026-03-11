include .env
export

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

.PHONY: backend frontend test lint install help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

backend: ## Start the backend API server
	cd backend && . .venv/bin/activate && PYTHONPATH=src uvicorn api.app:create_app --factory --port $(BACKEND_PORT)

frontend: ## Start the frontend dev server
	cd frontend && npm run dev

test: ## Run backend tests
	cd backend && .venv/bin/python -m pytest

test-v: ## Run backend tests (verbose)
	cd backend && .venv/bin/python -m pytest -v

lint: ## Lint frontend code
	cd frontend && npm run lint

install: ## Install all dependencies (backend + frontend)
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install
