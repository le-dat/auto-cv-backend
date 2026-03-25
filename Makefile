.PHONY: install lint format check-format type-check test clean help

# Variables
PYTHON = python3
PIP = $(PYTHON) -m pip
PYTEST = $(PYTHON) -m pytest
RUFF = $(PYTHON) -m ruff
MYPY = $(PYTHON) -m mypy

help:
	@echo "Available commands:"
	@echo "  install      - Install production and development dependencies"
	@echo "  lint         - Run ruff check"
	@echo "  format       - Run ruff format"
	@echo "  check-format - Run ruff format check"
	@echo "  type-check   - Run mypy type check"
	@echo "  test         - Run tests with coverage"
	@echo "  clean        - Remove temporary files"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

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
