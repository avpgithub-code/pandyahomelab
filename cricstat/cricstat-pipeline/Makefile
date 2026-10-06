.PHONY: help full recent build build-full register lint test docker-build clean

PROJECT_NAME := cricstat-pipeline
DOCKER_IMAGE := $(PROJECT_NAME):latest
PY := python3

help:
	@echo "cricstat-pipeline — Available targets:"
	@echo "  make full          — Download all_json.zip and ingest (removal detection on)"
	@echo "  make recent        — Download recently_added_7_json.zip and upsert"
	@echo "  make build         — Serving DB, incremental (full if none yet)"
	@echo "  make build-full    — Serving DB, rebuilt from scratch"
	@echo "  make register      — Download people.csv + names.csv into the raw store"
	@echo "  make lint          — ruff check"
	@echo "  make test          — pytest (no network)"
	@echo "  make docker-build  — Build the image (python:3.12-slim; CI/CD builds it, not the NAS)"
	@echo "  make clean         — Remove caches"

full:
	$(PY) -m presentation_logic.cli full

recent:
	$(PY) -m presentation_logic.cli recent

build:
	$(PY) -m presentation_logic.cli build

build-full:
	$(PY) -m presentation_logic.cli build --full

register:
	$(PY) -m presentation_logic.cli register

lint:
	$(PY) -m ruff check .

test:
	$(PY) -m pytest tests/ -q

docker-build:
	docker build -f docker/Dockerfile -t $(DOCKER_IMAGE) ..   # context = cricstat/ (needs sql/)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + || true
	rm -rf .pytest_cache .ruff_cache
