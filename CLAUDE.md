# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FINalyzer is a personal finance analyzer with AI-powered transaction categorization and natural language queries. It processes credit card statements (Chase, Amex, Coinbase) and uses LLMs for categorization and semantic search.

## Common Commands

```bash
make install      # Install all dependencies (uv sync + npm install)
make dev          # Start both backend and frontend
make backend      # Start only backend (FastAPI on port 8000)
make frontend     # Start only frontend (Next.js on port 3000)
make test         # Run backend tests with pytest
make lint         # Run ruff, mypy (backend) and eslint (frontend)
make format       # Auto-format with ruff and prettier
```

### Running a Single Test

```bash
uv run pytest backend/tests/test_query_engine.py -v          # Run one test file
uv run pytest backend/tests/test_query_engine.py::test_name -v  # Run specific test
```

## Architecture

### Backend (FastAPI + Python)

- **`backend/main.py`**: FastAPI app with all REST endpoints (/upload, /query, /transactions, /dashboard/*)
- **`backend/config.py`**: Pydantic settings from environment variables
- **`backend/models.py`**: Pydantic models for Transaction, TransactionSource, TransactionCategory enums
- **`backend/db/sqlite.py`**: SQLite database operations (transactions, uploaded files)
- **`backend/db/vector.py`**: ChromaDB vector store for semantic search

### Parsers (`backend/parsers/`)

Each parser extracts transactions from different statement formats:
- `chase_pdf.py`, `chase_csv.py`, `chase_report_pdf.py`: Chase formats
- `amex_csv.py`, `amex_year_end_pdf.py`: American Express formats
- `coinbase_csv.py`, `coinbase_pdf.py`: Coinbase Card formats

### Services (`backend/services/`)

- **`upload.py`**: Main upload flow - detect source, parse, categorize, tag, store
- **`categorizer.py`**: Fast rule-based categorization + background LLM categorization
- **`tagger.py`**: Fast merchant tagging + background LLM tagging
- **`query_engine.py`**: Natural language query processing with LLM
- **`dedup.py`**: File and transaction hash computation

### Frontend (Next.js + React)

- **`frontend/app/`**: Next.js App Router pages (/, /chat, /dashboard, /settings)
- **`frontend/components/`**: React components (UploadZone, TransactionTable, Navigation, etc.)

## Key Data Flow

1. **Upload**: File → detect source → parse → fast categorize/tag → save to SQLite → background LLM processing → vector store
2. **Query**: Natural language → LLM parses intent → SQL query + vector search → LLM summarizes results

## Configuration

Set in `.env` (copy from `.env.example`):
- `LLM_PROVIDER`: `ollama` (default) or `openai`
- `OLLAMA_MODEL`: Model for chat (default: `llama3.2`)
- `EMBEDDING_MODEL`: Model for embeddings (default: `nomic-embed-text`)
- `OPENAI_API_KEY`: Required if using OpenAI

Data stored in `~/.finalyzer/` (SQLite DB + ChromaDB vectors).

## Testing

Tests are in `backend/tests/`. Use pytest with asyncio support:
```bash
uv run pytest -v                    # All tests
uv run pytest -v -k "amex"          # Filter by name pattern
```
