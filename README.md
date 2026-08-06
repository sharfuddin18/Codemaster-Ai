<div align="center">

```text
  ____ ___  ____  _____ __  __    _    ____ _____ _____ ____        _ ___ 
 / ___/ _ \|  _ \| ____|  \/  |  / \  / ___|_   _| ____|  _ \      / \_ _|
| |  | | | | | | |  _| | |\/| | / _ \ \___ \ | | |  _| | |_) |    / _ \| | 
| |__| |_| | |_| | |___| |  | |/ ___ \ ___) || | | |___|  _ <    / ___ \ | 
 \____\___/|____/|_____|_|  |_/_/   \_\____/ |_| |_____|_| \_\  /_/   \_\_|


Codemaster-AI 🚀

# Your Private, On-Device AI Pair Programmer
* An agent-driven, terminal-first coding engine that indexes your local repository, understands AST context, and generates verified git patches—without sending a single byte to external servers.

# Why Codemaster-AI • Key Features • System Architecture • Recent Iterations • Quickstart • TUI & CLI Workflow • MCP Server • License

 💡 Why I Built This
Traditional AI coding assistants often feel like basic API wrappers around third-party endpoints. Built with ☕ and late-night persistence by Sharfuddin Ahmed (@sharfuddin18) — self-taught vibe coder, builder, and self-deploying dev — Codemaster-AI addresses three core developer priorities:

 ⚡ Terminal-First Workflow: Eliminates context switching by living directly inside your terminal UI or command line.

 🔒 Absolute Code Privacy: Runs 100% locally on your hardware via Ollama, ensuring zero data leakage or external server transmission.

 🧠 Full-Project Context Awareness: Maps real repository relationships and AST structure rather than reading a single isolated file, preventing hallucinated imports or broken signatures.

                            ✨ Key Features & Specialized Agents

             Feature                                                   Description

🤖 Code Reviewer AgentScans - codebases for anti-patterns, edge cases, and performance bottlenecks before committing.

🔍 Explainer Agent - Walks through complex functions, class relationships, and structural logic in simple terms.

🛠️ Code Generator Agent - Drafts clean, typed, production-ready code blocks tailored specifically to your project context.
🌲 Smart Tree AST Indexing - Traverses project directories while ignoring noise (node_modules, .git, venv) to map layout accurately.

🔎 Hybrid Search (Dense + Sparse) - Merges Vector Semantic Search (all-MiniLM-L6-v2) with BM25 Keyword Search (rank-bm25) for exact identifier matching.

🧩 Unified Git Patch Engine - Outputs standard .patch files instead of raw markdown blocks, allowing ai-fix to apply code directly via git apply.

🔌 Native MCP Server - Exposes Model Context Protocol REST endpoints for external editor integrations (VS Code, Cursor, Zed).


                        🏗️ System Architecture
┌────────────────────────────────────────────────────────────────────────┐
│                        DEVELOPER INTERFACES                            │
│   Terminal UI (TUI)   │   PowerShell / Bash CLI   │   IDE via MCP     │
│                     (ai-generate / ai-fix)                             │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND CORE                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        MCP Router & Endpoints                    │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
│                                  │                                     │
│  ┌───────────────────────────────┴──────────────────────────────────┐  │
│  │                       SPECIALIZED AGENTS                         │  │
│  │   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐   │  │
│  │   │  Code Reviewer   │  │    Explainer     │  │  Generator   │   │  │
│  │   │      Agent       │  │      Agent       │  │    Agent     │   │  │
│  │   └──────────────────┘  └──────────────────┘  └──────────────┘   │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
│                                  │                                     │
│  ┌───────────────────────────────┴──────────────────────────────────┐  │
│  │                   SMART TREE AST + RAG ENGINE                    │  │
│  │   ┌─────────────────────────────┐  ┌─────────────────────────┐   │  │
│  │   │ Dense Vector Search         │  │ Sparse BM25 Keywords    │   │  │
│  │   │ (all-MiniLM-L6-v2)          │  │ (rank-bm25)             │   │  │
│  │   └─────────────────────────────┘  └─────────────────────────┘   │  │
│  └───────────────────────────────┬──────────────────────────────────┘  │
└──────────────────────────────────┼─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  LOCAL OLLAMA INFERENCE ENGINE                         │
│               qwen2.5-coder / llama3.1 / mistral-nemo                  │
└────────────────────────────────────────────────────────────────────────┘

               🚀 Recent Architecture & Feature Iterations

⚡ Phase 1: Performance & Caching (Engine Scalability)
*Incremental File Hashing: Computes MD5/SHA256 hashes during tree traversal to skip unchanged files and avoid redundant embedding generation.
*Persistent Local Vector Cache: Stores vector embeddings locally (.codemaster/cache.db) for instant startup times on repeat queries.
*Batch Embedding Pipeline: Processes code chunks in async batches to leverage multi-core CPU capabilities.

🧪 Phase 2: Test Suite Hardening & Mocking
*Hybrid Search Integration: Merged vector search with BM25 keyword matching to accurately target specific code identifiers.
*Direct Patch Application: Implemented patch generation workflows to safely apply automated adjustments directly to local file structures.

🔒 Security & Resilience
*Zero External Data Leakage: Local LLM orchestration keeps code strictly on your local machine.
*Defensive Output Parsing: Sanitizes raw LLM responses and handles non-dictionary returns gracefully to prevent API failures.
*App State Verification: Health routes verify server initialization (app.state.activated) prior to processing generation requests.

                🧰 Tech Stack

      Domain                            Technology
* Language & Runtime             Python 3.12
* API Framework                  FastAPI + Pydantic (V2)
* Local LLM Engine               Ollama
* Vector Search / RAG	           Sentence-Transformers (all-MiniLM-L6-v2) + BM25 (rank-bm25)
* CLI & Automation               PowerShell 7 native scripts (ai-generate, ai-fix)
* Containerization               Docker Desktop
* Testing & CI/CD	               Pytest, Pytest-Cov, Respx (Validated on Python 3.10 & 3.11 via GitHub Actions)

 🚀 Quickstart

   Prerequisites
* Python: 3.12 or higher
* Ollama: Installed and running locally (Download Ollama)
* Docker Desktop: (Optional, if running containerized)
* Recommended Local Model:  ollama pull qwen2.5-coder:7b

1. Clone & Set Up
git clone [https://github.com/sharfuddin18/codemaster-ai.git](https://github.com/sharfuddin18/codemaster-ai.git)
cd codemaster-ai

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows PowerShell: .\venv\Scripts\Activate.ps1

# Install core & backend dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt

# Install CLI commands in editable mode
pip install -e .

2. Configure Environment
Set environment variables to point to your local Ollama instance:
export LLM_PROVIDER=ollama
export OLLAMA_ENABLED=true
export OLLAMA_BASE_URL=http://localhost:11434

3. Run Backend Server
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
(Interactive API documentation will be available at http://localhost:8000/docs)

 💻 TUI & CLI Workflow

Option 1: Interactive Terminal UI
Launch the interactive TUI for session-based coding and repository exploration:
python run_tui.py

Option 2: CLI Native Helpers (PowerShell / Bash)
Run quick actions directly from your terminal:
* Fast Terminal Code Generation:  ai-generate -Prompt "Create a FastAPI route for user authentication"
* Instant Terminal Code Fix:  ai-fix -File "./backend/app/routes/generation.py"

Option 3: REST API Endpoint (Curl)
curl -X POST http://localhost:8000/generate-code \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write an async Python function to calculate Fibonacci numbers with memoization"
  }'

🔌 MCP (Model Context Protocol)
Codemaster-AI exposes MCP-compliant REST endpoints for IDE and editor integrations.

Search Codebase Context
curl -X POST http://localhost:8000/mcp/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "database connection handler", "top_k": 3}'

Request Code Patch Generation
curl -X POST http://localhost:8000/mcp/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Add error handling and automatic retry strategy to DB pool initialization",
    "language": "python"
  }'


 🧪 Test Suite & Benchmarks
Status: 🟢 20/20 Unit & Integration Tests Passing (Validated across Python 3.10 and 3.11 via GitHub Actions CI/CD)

Bash
# Run tests locally
PYTHONPATH=.:backend:backend/app pytest -v

# Run tests with coverage output
pytest --cov=backend/app tests/

# Run benchmark harness
python run_benchmark.py

 🤝 Let's Connect
I’m actively iterating on Codemaster-AI to make it faster, smarter, and seamlessly integrated with local workflows. If you have ideas for new specialized agents, context improvements, or bug reports, feel free to open an issue or submit a Pull Request.

Author: Sharfuddin Ahmed (@sharfuddin18)

 📜 License
MIT License — UNSTOPPABLE EDITION
Copyright (c) 2025 Sharfuddin Ahmed

Permission is hereby GRANTED—without restriction, without apology, and without delay—to any digital architect, engineer, or code-warrior who secures a copy of this Software and its associated documentation (the “Software”). You are authorized to deploy, weaponize, modify, merge, publish, distribute, sublicense, and profit from digital creations forged from this codebase.

THE CORE MANDATE:
The original copyright notice and this declaration of absolute, unrestricted freedom MUST be carried forward into all copies or substantial portions of the Software. The savage, open-source spirit of Codemaster-AI is not a suggestion; it is a requirement.

DISCLAIMER OF LIABILITY:
THE SOFTWARE IS PROVIDED "AS IS," VOID OF WARRANTIES OR PROMISES. SHARFUDDIN AHMED, AND ANY CONTRIBUTORS THERETO, SHALL NOT BE HELD LIABLE IN CONTRACT, TORT, OR DIGITAL COMBAT FOR ANY SYSTEM FAILURE, DATA CATASTROPHE, OR UNINTENDED CHAOS ARISING FROM THE DEPLOYMENT OR MODIFICATION OF THIS POWER.

EXECUTE WITH INTENT:
OWN IT. BREAK IT. EVOLVE IT. BUT NEVER CAGE IT.
