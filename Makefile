.PHONY: up down build logs train demo test lint fmt help

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

train:
	python scripts/train_fraud_model.py

demo:
	bash scripts/demo_flow.sh

test:
	pytest

lint:
	ruff check services tests scripts

fmt:
	ruff format services tests scripts

help:
	@echo "Available targets:"
	@echo "  up      - Start all services (detached)"
	@echo "  down    - Stop all services"
	@echo "  build   - Rebuild Docker images"
	@echo "  logs    - Tail all service logs"
	@echo "  train   - Train fraud model and save to models/"
	@echo "  demo    - Run end-to-end demo flow against running stack"
	@echo "  test    - Run unit tests"
	@echo "  lint    - Run ruff linter"
	@echo "  fmt     - Run ruff formatter"
