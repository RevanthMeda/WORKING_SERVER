.PHONY: help install install-dev test test-unit test-integration test-e2e test-performance
.PHONY: lint format type-check security-check quality-check
.PHONY: clean build run docker-build docker-run
.PHONY: pre-commit setup-pre-commit migrate db-upgrade db-downgrade
.PHONY: docs serve-docs coverage-report

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements.txt -r requirements-test.txt
	pip install -e .

# Testing
test: ## Run all tests
	python -m pytest tests/ -v

test-unit: ## Run unit tests only
	python -m pytest tests/unit/ -v --cov=. --cov-report=html --cov-report=term-missing

test-integration: ## Run integration tests only
	python -m pytest tests/integration/ -v

test-e2e: ## Run end-to-end tests only
	python -m pytest tests/e2e/ -v -m "not slow"

test-performance: ## Run performance tests
	python -m pytest tests/performance/ -v -m performance
	python run_performance_tests.py --test-type locust --duration 60 --users 10

test-coverage: ## Run tests with coverage report
	python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing --cov-fail-under=80

# Code Quality
lint: ## Run linting checks
	flake8 . --max-line-length=127 --extend-ignore=E203,W503
	pylint . --exit-zero --output-format=text --reports=no --score=yes

format: ## Format code with black and isort
	black . --line-length=127
	isort . --profile=black --line-length=127

format-check: ## Check code formatting
	black --check --diff . --line-length=127
	isort --check-only --diff . --profile=black --line-length=127

type-check: ## Run type checking with mypy
	mypy . --ignore-missing-imports --no-strict-optional

security-check: ## Run security checks
	bandit -r . -f json -o bandit-report.json --exclude="tests,migrations,venv,env"
	bandit -r . -f txt --exclude="tests,migrations,venv,env"
	safety check

complexity-check: ## Analyze code complexity
	radon cc . --exclude="tests,migrations,venv,env" --show-complexity --min=B
	radon mi . --exclude="tests,migrations,venv,env" --show --min=B

quality-report: ## Generate comprehensive quality report
	python scripts/code_quality.py --action report

quality-fix: ## Fix code quality issues automatically
	python scripts/code_quality.py --action fix

quality-metrics: ## Collect detailed quality metrics
	python scripts/quality_metrics.py

quality-automation: ## Run full quality automation
	python scripts/quality_automation.py --mode full

quality-dashboard: ## Generate quality dashboard
	python scripts/debt_dashboard.py

debt-analysis: ## Run technical debt analysis
	python scripts/technical_debt_tracker.py --action-plan

quality-check: format-check lint type-check security-check complexity-check ## Run all code quality checks

# Pre-commit
setup-pre-commit: ## Set up pre-commit hooks
	pre-commit install
	pre-commit install --hook-type commit-msg

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

# Database
migrate: ## Create a new database migration
	flask db migrate -m "$(MESSAGE)"

db-upgrade: ## Apply database migrations
	flask db upgrade

db-downgrade: ## Rollback database migration
	flask db downgrade

db-init: ## Initialize database
	flask db init

# Development
run: ## Run the development server
	python app.py

run-debug: ## Run the development server in debug mode
	FLASK_ENV=development FLASK_DEBUG=1 python app.py

run-production: ## Run the production server
	gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Docker
docker-build: ## Build Docker image
	docker build -t sat-report-generator .

docker-run: ## Run Docker container
	docker run -p 5000:5000 --env-file .env sat-report-generator

docker-compose-up: ## Start services with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop services with docker-compose
	docker-compose down

# Documentation
docs: ## Build documentation
	cd docs && make html

serve-docs: ## Serve documentation locally
	cd docs/_build/html && python -m http.server 8000

# Utilities
clean: ## Clean up build artifacts and cache files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf performance_results/
	rm -rf test_screenshots/

build: clean ## Build the package
	python -m build

coverage-report: ## Generate and open coverage report
	python -m pytest tests/ --cov=. --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

# Performance monitoring
monitor-performance: ## Run continuous performance monitoring
	python run_performance_tests.py --test-type all --duration 300 --users 50

benchmark: ## Run database and API benchmarks
	python run_performance_tests.py --test-type database
	python run_performance_tests.py --test-type api

# Security
security-audit: ## Run comprehensive security audit
	bandit -r . -f json -o security-audit.json
	safety check --json --output safety-audit.json
	@echo "Security audit reports generated"

# CI/CD helpers
ci-install: ## Install dependencies for CI
	pip install --upgrade pip
	pip install -r requirements.txt -r requirements-test.txt

ci-test: ## Run tests in CI environment
	python -m pytest tests/ -v --tb=short --cov=. --cov-report=xml --cov-fail-under=80

ci-quality: ## Run quality checks in CI environment
	black --check .
	isort --check-only .
	flake8 .
	mypy . --ignore-missing-imports
	bandit -r . -f txt

# Environment setup
setup-dev: install-dev setup-pre-commit ## Set up development environment
	@echo "Development environment setup complete!"
	@echo "Run 'make run' to start the development server"

setup-production: install ## Set up production environment
	@echo "Production environment setup complete!"
	@echo "Run 'make run-production' to start the production server"

# Database seeding
seed-db: ## Seed database with sample data
	python -c "from tests.factories import *; from tests.performance.performance_config import create_performance_test_data; create_performance_test_data(db.session, 50, 200)"

# Monitoring and health checks
health-check: ## Check application health
	curl -f http://localhost:5000/health || echo "Application is not running"

load-test: ## Run load test against running application
	python run_performance_tests.py --test-type locust --host http://localhost:5000 --users 20 --duration 120

# Deployment helpers
deploy-staging: ## Deploy to staging environment
	@echo "Deploying to staging..."
	# Add staging deployment commands here

deploy-production: ## Deploy to production environment
	@echo "Deploying to production..."
	# Add production deployment commands here

# Backup and restore
backup-db: ## Backup database
	@echo "Creating database backup..."
	# Add database backup commands here

restore-db: ## Restore database from backup
	@echo "Restoring database from backup..."
	# Add database restore commands here