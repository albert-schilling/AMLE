# Define the default shell to use
SHELL := /bin/bash

# .PHONY tells Make that these targets are commands, not actual files on disk
.PHONY: format lint setup test run approve decline reset help \
	obs-up obs-down obs-check obs-usage db-up db-down db-check test-db test-embedding kb-index

# The default target that runs if you just type 'make'
help:
	@echo "Available commands:"
	@echo "  make setup   - Install dependencies and prepare the project"
	@echo "  make test    - Run the project test suite"
	@echo "  make format  - Format the code using ruff"
	@echo "  make lint    - Lint the code using ruff"
	@echo "  make run     - Run the classifier script"
	@echo "  make approve TICKET=T-1 NOTE=\"...\" - A human takes over a paused ticket"
	@echo "  make decline TICKET=T-1 NOTE=\"...\" - No human takes over a paused ticket"
	@echo "  make reset   - Delete saved runs, trace and results (paused tickets are lost)"
	@echo "  make obs-up    - Start the local monitoring stack (Grafana: http://localhost:3000)"
	@echo "  make obs-down  - Stop the monitoring stack (data is kept)"
	@echo "  make obs-check - Check that all monitoring services are ready"
	@echo "  make obs-usage - Show disk usage of the monitoring data"
	@echo "  make db-up    - Start PostgreSQL and wait until it is healthy"
	@echo "  make db-down  - Stop PostgreSQL (data is kept)"
	@echo "  make db-check - Check that PostgreSQL and pgvector are ready"
	@echo "  make test-db  - Run the tests that need PostgreSQL (database knowledge_test)"
	@echo "  make test-embedding - Run the one test with the real embedding model"
	@echo "  make kb-index - Embed data/knowledge_base into PostgreSQL (first run downloads the model)"

setup:
	uv sync

test:
	uv run pytest

format:
	uv run ruff format

lint:
	uv run ruff check

run:
	@echo "REQUIREMENT: Anthropic API Key in the environment"
	@echo "WARNING: Executing this script will make calls to the Anthropic API causing potential charges."
	@echo "Running classifier script..."
	uv run ticket-classifier run


# Answer a paused ticket; no model call. Usage: make approve TICKET=T-1 NOTE="..."
approve decline:
	@test -n "$(TICKET)" || { echo "Usage: make $@ TICKET=<id> [NOTE=\"...\"]"; exit 2; }
	uv run ticket-classifier resume "$(TICKET)" --$@ --note "$(NOTE)"

# Start from scratch: the next run classifies every ticket again.
reset:
	@echo "WARNING: deletes saved runs; paused tickets cannot be resumed afterwards."
	rm -f output/checkpoints.db output/trace.jsonl output/results.json

# Local monitoring stack, see monitoring/README.md.
COMPOSE := docker compose -f monitoring/docker-compose.yml
# Prometheus, Tempo and Loki have no host ports (internal network), so they are
# checked from inside the network with the curl in the Grafana image. Retries short
# hiccups; on failure, prints the service's reason (e.g. Loki's /ready message).
IN_NETWORK := $(COMPOSE) exec -T grafana curl -s -m 5 --retry 3 --retry-delay 2 \
	--retry-all-errors --fail-with-body

obs-up:
	$(COMPOSE) up -d
	@echo "Grafana: http://localhost:3000 (user admin). Check readiness: make obs-check"

obs-down:
	$(COMPOSE) down

obs-check:
	@fail=0; \
	curl -sf -o /dev/null localhost:3000/api/health && echo "OK    grafana" || { echo "FAIL  grafana"; fail=1; }; \
	curl -sf -o /dev/null localhost:13133 && echo "OK    collector" || { echo "FAIL  collector"; fail=1; }; \
	out=$$($(IN_NETWORK) http://prometheus:9090/-/ready) && echo "OK    prometheus" || { echo "FAIL  prometheus: $$out"; fail=1; }; \
	out=$$($(IN_NETWORK) http://tempo:3200/ready) && echo "OK    tempo" || { echo "FAIL  tempo: $$out"; fail=1; }; \
	out=$$($(IN_NETWORK) http://loki:3100/ready) && echo "OK    loki" || { echo "FAIL  loki: $$out"; fail=1; }; \
	exit $$fail

obs-usage:
	@docker system df -v | grep -E '^VOLUME NAME|^ticket-classifier-monitoring_'

# Local PostgreSQL with pgvector for the knowledge base.
DB_COMPOSE := docker compose -f database/docker-compose.yml
DB_PSQL := $(DB_COMPOSE) exec -T postgres sh -c 'psql -At -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

db-up:
	$(DB_COMPOSE) up -d --wait

db-down:
	$(DB_COMPOSE) down

db-check:
	@$(DB_COMPOSE) exec -T postgres sh -c 'pg_isready -q -h 127.0.0.1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' \
		&& echo "OK    postgres" || { echo "FAIL  postgres"; exit 1; }
	@version=$$(echo "select default_version from pg_available_extensions where name = 'vector'" | $(DB_PSQL)); \
	test -n "$$version" && echo "OK    pgvector $$version" || { echo "FAIL  pgvector"; exit 1; }

# Tests that need PostgreSQL use their own database; each test is rolled back.
test-db:
	@echo "select 1 from pg_database where datname = 'knowledge_test'" | $(DB_PSQL) | grep -q 1 \
		|| echo "create database knowledge_test" | $(DB_PSQL)
	@set -a; . database/.env; set +a; \
	KNOWLEDGE_TEST_DATABASE_URL="postgresql://$$POSTGRES_USER:$$POSTGRES_PASSWORD@localhost:5432/knowledge_test" \
		uv run pytest -m postgres

# The real model, from output/fastembed (downloaded on first use).
test-embedding:
	RUN_EMBEDDING_TEST=1 uv run pytest tests/test_embedder.py

# Local embedding model, no API cost. Skipped if the documents are unchanged.
kb-index:
	uv run ticket-classifier kb-index
