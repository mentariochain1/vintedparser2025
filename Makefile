.PHONY: help install dev test lint format clean build run docker-build docker-run

# Default target
help:
	@echo "Available commands:"
	@echo "  install     Install production dependencies"
	@echo "  dev         Install development dependencies"
	@echo "  test        Run tests"
	@echo "  lint        Run linting"
	@echo "  format      Format code"
	@echo "  clean       Clean build artifacts"
	@echo "  build       Build Docker image"
	@echo "  run         Run the application"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run  Run with Docker Compose"

# Install production dependencies
install:
	poetry install --only main

# Install development dependencies
dev:
	poetry install
	pre-commit install

# Run tests
test:
	poetry run pytest

# Run tests with coverage
test-cov:
	poetry run pytest --cov=src --cov-report=html --cov-report=term

# Run linting
lint:
	poetry run ruff check src tests
	poetry run mypy src

# Format code
format:
	poetry run ruff format src tests
	poetry run ruff check --fix src tests

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +

# Build Docker image
docker-build:
	docker build -t vinted-parser-bot .

# Run with Docker Compose
docker-run:
	docker-compose up --build

# Run the application locally
run:
	poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Run production server
run-prod:
	poetry run gunicorn -k uvicorn.workers.UvicornWorker -c gunicorn_conf.py src.main:app

# Database migrations (placeholder for future Supabase migrations)
migrate:
	@echo "Database migrations will be handled by Supabase CLI"

# Setup development environment
setup-dev: dev
	cp .env.example .env
	@echo "Development environment setup complete!"
	@echo "Please edit .env file with your configuration"