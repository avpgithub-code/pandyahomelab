.PHONY: help data benchmark lint test docker-build docker-run docker-stop clean

PROJECT_NAME := nlp-ewt-hmm
DOCKER_IMAGE := $(PROJECT_NAME):latest
HOST_PORT := 8023
CONTAINER_PORT := 8000

help:
	@echo "nlp-ewt-hmm — Available targets:"
	@echo "  make data          — Download UD English EWT train/test into data/ewt/"
	@echo "  make benchmark     — Re-run the 3d gate benchmark (scripts/benchmark_gate.py)"
	@echo "  make lint          — Run black, flake8, mypy"
	@echo "  make test-unit     — Run unit tests"
	@echo "  make test-cov      — Run tests with coverage"
	@echo "  make docker-build  — Build Docker image"
	@echo "  make docker-run    — Run container locally"
	@echo "  make docker-stop   — Stop running container"
	@echo "  make clean         — Remove __pycache__ and .pyc files"

data:
	python3 scripts/fetch_ewt.py --data-dir data/ewt

benchmark:
	python3 scripts/benchmark_gate.py --data-dir data/ewt

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
	@echo "Running container on host port $(HOST_PORT)..."
	docker run -p 127.0.0.1:$(HOST_PORT):$(CONTAINER_PORT) --name $(PROJECT_NAME)-container $(DOCKER_IMAGE)

docker-stop:
	@echo "Stopping container..."
	docker stop $(PROJECT_NAME)-container || true
	docker rm $(PROJECT_NAME)-container || true

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
