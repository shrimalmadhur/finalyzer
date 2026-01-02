# FINalyzer

Personal finance analyzer with AI-powered categorization and natural language queries. All data stays local.

<table>
  <tr>
    <td><img src="images/1.png" width="400" alt="Upload" /></td>
    <td><img src="images/2.png" width="400" alt="Dashboard" /></td>
  </tr>
  <tr>
    <td><img src="images/3.png" width="400" alt="Ask AI" /></td>
    <td><img src="images/4.png" width="400" alt="Settings" /></td>
  </tr>
</table>

## Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.ai/) (for local LLM) or OpenAI API key

## Quick Start

```bash
# Install everything (uv, node, dependencies)
make install

# Pull Ollama models (for local LLM)
ollama pull llama3.2
ollama pull nomic-embed-text

# Start the app
make dev
```

Open **http://localhost:3000**

### Using OpenAI Instead of Ollama

```bash
cp .env.example .env
```

Edit `.env`:
```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

## Supported Formats

| Source | Formats |
|--------|---------|
| Chase | PDF, CSV, Report PDF |
| Amex | CSV, Year-End PDF |
| Coinbase | CSV, PDF |

## Commands

```bash
make dev       # Start backend + frontend
make test      # Run tests
make lint      # Lint code
make format    # Format code
make clean     # Remove ~/.finalyzer/ data
```

## Data Storage

All data stored locally in `~/.finalyzer/`

## License

MIT
