# Define the default shell to use
SHELL := /bin/bash

# .PHONY tells Make that these targets are commands, not actual files on disk
.PHONY: format lint setup test run approve decline help

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
	uv run ticket-classifier


# Answer a paused ticket; no model call. Usage: make approve TICKET=T-1 NOTE="..."
approve decline:
	@test -n "$(TICKET)" || { echo "Usage: make $@ TICKET=<id> [NOTE=\"...\"]"; exit 2; }
	uv run ticket-classifier --resume "$(TICKET)" --$@ --note "$(NOTE)"
