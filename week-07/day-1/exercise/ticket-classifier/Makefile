# Define the default shell to use
SHELL := /bin/bash

# .PHONY tells Make that these targets are commands, not actual files on disk
.PHONY: setup test run help

# The default target that runs if you just type 'make'
help:
	@echo "Available commands:"
	@echo "  make setup   - Install dependencies and prepare the project"
	@echo "  make test    - Run the project test suite"
	@echo "  make run     - Run the classifier script"

setup:
	uv sync

test:
	uv run pytest

run:
	@echo "REQUIREMENT: Anthropic API Key in the environment"
	@echo "WARNING: Executing this script will make calls to the Anthropic API causing potential charges."
	@echo "Running classifier script..."
	uv run ticket-classifier
