.PHONY: dev install backend frontend test lint format clean sample help check-deps

# Default target
help:
	@echo "FINalyzer - Personal Finance Analyzer"
	@echo ""
	@echo "Usage:"
	@echo "  make install   - Install all dependencies (including uv, node if needed)"
	@echo "  make dev       - Start both backend and frontend in dev mode"
	@echo "  make backend   - Start only the backend server"
	@echo "  make frontend  - Start only the frontend server"
	@echo "  make test      - Run backend tests"
	@echo "  make lint      - Run linters on all code"
	@echo "  make format    - Auto-format all code"
	@echo "  make clean     - Remove local data (~/.finalyzer/)"

# Check and install system dependencies
check-deps:
	@echo "Checking dependencies..."
	@# Check for uv
	@if ! command -v uv &> /dev/null; then \
		echo "Installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		echo "Please restart your terminal or run: source ~/.bashrc (or ~/.zshrc)"; \
	else \
		echo "✓ uv found"; \
	fi
	@# Check for node/npm
	@if ! command -v node &> /dev/null; then \
		echo "Node.js not found. Installing..."; \
		if command -v brew &> /dev/null; then \
			brew install node; \
		elif command -v apt-get &> /dev/null; then \
			curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs; \
		else \
			echo "Please install Node.js manually: https://nodejs.org/"; \
			exit 1; \
		fi \
	else \
		echo "✓ node found ($$(node --version))"; \
	fi

# Install all dependencies
install: check-deps
	@echo ""
	@echo "Installing Python dependencies..."
	uv sync
	@echo ""
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo ""
	@echo "✓ Done! Run 'make dev' to start the application."

# Start everything in development mode
dev:
	@echo "Starting FINalyzer in development mode..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	@make -j2 backend frontend

# Start backend only
backend:
	@echo "Starting backend server..."
	@echo "Note: Using settings from .env file (ignoring shell environment variables)"
	env -u LLM_PROVIDER uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend only
frontend:
	@echo "Starting frontend server..."
	cd frontend && npm run dev

# Run tests
test:
	@echo "Running backend tests..."
	uv run pytest -v

# Lint all code
lint:
	@echo "Linting Python code..."
	uv run ruff check backend/
	uv run mypy backend/
	@echo "Linting TypeScript code..."
	cd frontend && npm run lint

# Format all code
format:
	@echo "Formatting Python code..."
	uv run ruff format backend/
	uv run ruff check --fix backend/
	@echo "Formatting TypeScript code..."
	cd frontend && npm run format

# Clean local data
clean:
	@echo "Removing local data..."
	rm -rf ~/.finalyzer/
	@echo "Done! All local data has been removed."

# Load sample data (for development/testing)
sample:
	@echo "Loading sample transactions..."
	uv run python -c "from backend.db.sqlite import db; print(f'Database has {db.get_transaction_count()} transactions')"

