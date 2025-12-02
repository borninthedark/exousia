# Exousia Development Makefile
# Common development tasks

.PHONY: help install format lint test test-cov api-dev clean build push

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Exousia Development Commands"
	@echo "============================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install development dependencies
	pip install -r api/requirements.txt
	pre-commit install

format: ## Format code with black and isort
	black api/ tools/
	isort api/ tools/

lint: ## Run all linters (black, ruff, pylint, mypy)
	@echo "Running black..."
	black --check api/ tools/
	@echo "Running isort..."
	isort --check-only api/ tools/
	@echo "Running ruff..."
	ruff check api/ tools/
	@echo "Running pylint..."
	pylint api/**/*.py tools/*.py || true
	@echo "Running mypy..."
	mypy api/ || true

test: ## Run pytest tests
	pytest api/tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	pytest api/tests/ -v --tb=short --cov=api --cov-report=term --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

api-dev: ## Start API development server with hot-reload
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

api-podman: ## Start API with podman-compose
	podman-compose up -d
	@echo "API running at http://localhost:8000"
	@echo "Docs at http://localhost:8000/api/docs"

api-stop: ## Stop podman-compose services
	podman-compose down

api-logs: ## View API logs
	podman-compose logs -f api

clean: ## Clean generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage coverage.xml
	rm -f Containerfile.*.generated exousia.db

build-atomic: ## Build atomic Containerfile from YAML
	python3 tools/yaml-to-containerfile.py \
		--config adnyeus.yml \
		--image-type fedora-sway-atomic \
		--output Containerfile.atomic.generated

build-bootc: ## Build bootc Containerfile from YAML
	python3 tools/yaml-to-containerfile.py \
		--config adnyeus.yml \
		--image-type fedora-bootc \
		--enable-plymouth \
		--output Containerfile.bootc.generated

validate: ## Validate YAML configuration
	python3 tools/yaml-to-containerfile.py \
		--config adnyeus.yml \
		--validate

build-api-image: ## Build API container image with podman
	podman build -t exousia-api:latest -f api/Containerfile .

run-api-container: ## Run API container with podman
	podman run -d \
		-p 8000:8000 \
		-e DATABASE_URL="sqlite+aiosqlite:///./exousia.db" \
		--name exousia-api \
		exousia-api:latest

ci-lint: ## Run CI linting checks (like GitHub Actions)
	@echo "==> Running CI linting checks..."
	black --check api/ tools/
	isort --check-only api/ tools/
	ruff check api/ tools/
	pylint api/**/*.py tools/*.py || true
	mypy api/ || true
	@echo "==> CI linting complete"

ci-test: ## Run CI tests (like GitHub Actions)
	@echo "==> Running CI tests..."
	pytest api/tests/ -v --tb=short --cov=api --cov-report=term
	@echo "==> CI tests complete"

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

shell: ## Open Python shell with API imports
	python3 -c "from api import *; import IPython; IPython.embed()"

# Original build/push targets
build: ## Build bootc image with podman
	podman build -t exousia:latest -f Containerfile.atomic .

push: ## Push bootc image to registry
	podman push exousia:latest
