.PHONY: help lint test docker-build docker-run docker-stop clean

TEMPLATE_VERSION := 1.0
PROJECT_NAME := ml-project-template
DOCKER_IMAGE := $(PROJECT_NAME):latest

help:
	@echo "ML Project Template — Available targets:"
	@echo "  make lint          — Run black, flake8, mypy"
	@echo "  make test-unit     — Run unit tests"
	@echo "  make test-cov      — Run tests with coverage"
	@echo "  make docker-build  — Build Docker image"
	@echo "  make docker-run    — Run container locally"
	@echo "  make docker-stop   — Stop running container"
	@echo "  make clean         — Remove __pycache__ and .pyc files"

lint:
	@echo "Linting code..."
	black --line-length 100 .
	flake8 --max-line-length=100 --ignore=E501,W503 .
	mypy . --ignore-missing-imports

test-unit:
	@echo "Running unit tests..."
	pytest tests/ -v -m "not e2e"

test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=. --cov-report=html --cov-report=term

docker-build:
	@echo "Building Docker image: $(DOCKER_IMAGE)"
	docker build -f docker/Dockerfile -t $(DOCKER_IMAGE) .

docker-run:
	@echo "Running container..."
	docker run -p 8000:8000 --name $(PROJECT_NAME)-container $(DOCKER_IMAGE)

docker-stop:
	@echo "Stopping container..."
	docker stop $(PROJECT_NAME)-container || true
	docker rm $(PROJECT_NAME)-container || true

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
