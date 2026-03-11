SHELL := /bin/bash

ROOT_PYTHON ?= python3
VENV ?= .venv
VENV_DIR := $(abspath $(VENV))
PYTHON := $(VENV_DIR)/bin/python
PIP := $(PYTHON) -m pip
NPM ?= npm

BACKTESTER_ARGS ?=
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

.PHONY: help venv \
	build check test \
	build-backtester build-strategizer build-portfolio build-observer-backend observer-frontend-build \
	test-backtester test-strategizer test-portfolio test-observer-backend observer-frontend-lint \
	install install-backtester install-strategizer install-portfolio install-observer observer-frontend-install \
	backtester-run observer-backend observer-frontend

$(PYTHON):
	$(ROOT_PYTHON) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install build pytest

venv: $(PYTHON) ## Create the root Python virtualenv and core tooling

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_.-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

build: build-backtester build-strategizer build-portfolio build-observer-backend observer-frontend-build ## Build all projects

test: test-backtester test-strategizer test-portfolio test-observer-backend observer-frontend-lint ## Test all projects (frontend uses lint)

check: build test ## Build and test all projects

install: venv install-portfolio install-strategizer install-backtester install-observer observer-frontend-install ## Install all project dependencies

build-backtester: venv ## Build the backtester package
	$(PYTHON) -m build backtester

build-strategizer: venv ## Build the strategizer package
	$(PYTHON) -m build strategizer

build-portfolio: venv ## Build the portfolio package
	$(PYTHON) -m build portfolio

build-observer-backend: venv ## Build the observer backend package
	$(PYTHON) -m build observer/backend

observer-frontend-build: ## Build the observer frontend
	cd observer/frontend && $(NPM) run build

test-backtester: venv ## Run backtester tests
	cd backtester && $(PYTHON) -m pytest -q

test-strategizer: venv ## Run strategizer tests
	cd strategizer && $(PYTHON) -m pytest -q

test-portfolio: venv ## Run portfolio tests
	cd portfolio && $(PYTHON) -m pytest -q

test-observer-backend: venv ## Run observer backend tests
	cd observer/backend && $(PYTHON) -m pytest -q

observer-frontend-lint: ## Lint the observer frontend
	cd observer/frontend && $(NPM) run lint

install-backtester: venv ## Install backtester in editable mode
	cd backtester && $(PYTHON) -m pip install -e ".[dev]"

install-strategizer: venv ## Install strategizer in editable mode
	cd strategizer && $(PYTHON) -m pip install -e ".[dev]"

install-portfolio: venv ## Install portfolio in editable mode
	cd portfolio && $(PYTHON) -m pip install -e ".[dev]"

install-observer: venv ## Install observer backend dependencies
	cd observer/backend && $(PYTHON) -m pip install -e ".[dev]"

observer-frontend-install: ## Install observer frontend dependencies
	cd observer/frontend && $(NPM) install

backtester-run: venv ## Run a backtest (requires BACKTESTER_CONFIG=path/to/config.yaml)
ifndef BACKTESTER_CONFIG
	$(error BACKTESTER_CONFIG is required, e.g. make backtester-run BACKTESTER_CONFIG=configs/orb_5m_example.yaml)
endif
	cd backtester && $(PYTHON) -m src.runner "$(BACKTESTER_CONFIG)" $(BACKTESTER_ARGS)

observer-backend: venv ## Start the observer backend API server
	cd observer/backend && PYTHONPATH=src $(PYTHON) -m uvicorn api.app:create_app --factory --port $(BACKEND_PORT)

observer-frontend: ## Start the observer frontend dev server
	$(MAKE) -C observer frontend FRONTEND_PORT=$(FRONTEND_PORT)
