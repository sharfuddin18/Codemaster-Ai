<div align="center">

```text
  ____  ___  ____  _____ __  __   _   ____ _____ _____ ____             _   ___ 
 / ___|/ _ \|  _ \| ____|  \/  | / \ / ___|_   _| ____|  _ \           / \ |_ _|
| |   | | | | | | |  _| | |\/| |/ _ \\___ \ | | |  _| | |_) |  _____  / _ \ | | 
| |___| |_| | |_| | |___| |  | / ___ \___) || | | |___|  _ <  |_____|/ ___ \| | 
 \____|\___/|____/|_____|_|  |/_/   \_\____/ |_| |_____|_| \_\       /_/   \_\___|


# Codemaster-AI 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.txt)
[![Tests](https://img.shields.io/badge/Tests-26%20Passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)

A privacy-first, agent-driven, terminal-first local AI coding engine that indexes your
entire repository and performs real-world development tasks without sending code
to external servers.

> Built with ☕ and persistence by [Sharfuddin Ahmed (@sharfuddin18)](https://github.com/sharfuddin18).

---

## Table of Contents

1. [Why Codemaster-AI](#why-codemaster-ai)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Quickstart](#quickstart)
5. [MCP (Model Context Protocol)](#mcp-model-context-protocol)
6. [Testing](#testing)
7. [Contributing](#contributing)
8. [License](#license)

---

## Why Codemaster-AI?

Traditional AI coding assistants often act as thin API wrappers around cloud endpoints.
Codemaster-AI focuses on three developer priorities:

- **Terminal-first workflow** — work from the terminal or TUI without context switching.
- **Code privacy** — runs locally (via Ollama) so code never leaves your machine.
- **Full-project context** — indexes project AST and file relationships to avoid
  hallucinated imports and broken signatures.

## Features

- Local LLM orchestration with Ollama
- Hybrid retrieval: dense vectors (`all-MiniLM-L6-v2`) + BM25 keyword ranking
- Verified generation with provenance and citation checks
- Patch-based fixes that produce `.patch` files suitable for `git apply`
- Interactive TUI (`run_tui.py`) and CLI helpers (`ai-generate`, `ai-fix`)

## Architecture

High-level pipeline:

```
Terminal / CLI / TUI --> FastAPI backend (MCP router)
  --> Agents (Generator / Reviewer / Explainer)
  --> Hybrid RAG (Dense + Sparse) --> Local Ollama inference
```

- Specialized agents: Code Reviewer, Explainer, Generator
- Smart Tree indexing to skip noise (`node_modules`, `.git`)
- Patch generator: outputs clean `.patch` files for safe application

## Quickstart

### Prerequisites

- Ollama installed and running locally
- Python 3.12+
- (Optional) Docker Desktop

### Setup

```bash
git clone https://github.com/sharfuddin18/codemaster-ai.git
cd codemaster-ai

# Optional: virtual environment
python -m venv venv
source venv/bin/activate

# Install Python deps
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

### Environment

```bash
export LLM_PROVIDER=ollama
export OLLAMA_ENABLED=true
export OLLAMA_BASE_URL=http://localhost:11434
```

### Run backend

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open interactive docs at: http://localhost:8000/docs

## Usage examples

Terminal UI

```bash
python run_tui.py
```

CLI helpers (PowerShell)

```powershell
ai-generate -Prompt "Create a FastAPI route for user authentication"
ai-fix -File "./backend/app/routes/generation.py"
```

REST API (curl)

```bash
curl -X POST http://localhost:8000/generate-code \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Write an async Python function to calculate Fibonacci numbers with memoization"}'
```

## MCP (Model Context Protocol)

External editors can call local MCP endpoints to retrieve context, request
verified generation, or apply fixes.

Check capabilities

```bash
curl http://localhost:8000/mcp/capabilities
```

Retrieve context (hybrid search)

```bash
curl -X POST http://localhost:8000/mcp/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"database connection","top_k":5}'
```

Generate verified code

```bash
curl -X POST http://localhost:8000/mcp/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Create a helper to open a DB connection","language":"python"}'
```

Python MCP client example

```python
import requests

BASE = "http://localhost:8000/mcp"
print(requests.get(f"{BASE}/capabilities").json())

resp = requests.post(f"{BASE}/retrieve", json={"query":"open file","top_k":3})
print(resp.json())

gen = requests.post(f"{BASE}/generate", json={"prompt":"create helper","language":"python"})
print(gen.json())
```

## Testing

```bash
# Run unit tests
PYTHONPATH=.:backend:backend/app pytest -v

# Run benchmark harness
python run_benchmark.py
```

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` and open issues or PRs.

## License

This project is licensed under the MIT License — see `LICENSE.txt`.

---
