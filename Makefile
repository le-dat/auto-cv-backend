.PHONY: install lint format check-format type-check test clean help

# Variables
PYTHON = python3
VENV = .venv
BIN = $(VENV)/bin

# Check if we are inside a virtual env
ifdef VIRTUAL_ENV
	ENV_BIN =
else
	ENV_BIN = $(BIN)/
endif

PIP = $(ENV_BIN)pip
PYTEST = $(ENV_BIN)pytest
RUFF = $(ENV_BIN)ruff
MYPY = $(ENV_BIN)mypy

help:
	@echo "Available commands:"
	@echo "  install      - Install production and development dependencies"
	@echo "  lint         - Run ruff check"
	@echo "  format       - Run ruff format"
	@echo "  check-format - Run ruff format check"
	@echo "  type-check   - Run mypy type check"
	@echo "  test         - Run tests with coverage"
	@echo "  clean        - Remove temporary files"

$(BIN)/activate:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip

install:
	@if [ -z "$$VIRTUAL_ENV" ] && [ ! -d "$(VENV)" ]; then \
		$(MAKE) $(BIN)/activate; \
	fi
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	@if [ -d ".git" ]; then \
		$(BIN)/pre-commit install; \
	fi

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

check-format:
	$(RUFF) format --check .

type-check:
	$(MYPY) .

test:
	$(PYTEST) tests/ --cov=app --cov-report=term-missing

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -f .coverage
