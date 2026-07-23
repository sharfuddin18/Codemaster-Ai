Codemaster-AI 🚀
A privacy-first, agent-driven local AI coding engine designed to live inside your terminal, index your entire codebase, and handle real-world development tasks without sending your code to external servers.

Built with ☕ and late-night persistence by Sharfuddin Ahmed (@sharfuddin18) — self-taught vibe coder, builder, and self-deploying dev.

💡 Why I Built This
Traditional AI coding assistants often feel like basic API wrappers around third-party endpoints. Codemaster-AI was built to address three core developer needs:

Terminal-First Workflow — Eliminates context switching by living directly inside your terminal.

Absolute Code Privacy — Runs 100% locally on your hardware via Ollama, ensuring zero data leakage.

Full-Project Context Awareness — Maps project relationships rather than reading a single active file, preventing hallucinated imports or broken signatures.

🏗️ Architecture & How It Works
Instead of dumping massive raw files into a single context window, Codemaster-AI uses modular processing pipelines:

Plaintext
               ┌────────────────────────┐
               │    Terminal / CLI      │
               │ (ai-generate / ai-fix) │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │   FastAPI Backend      │
               └───────────┬────────────┘
                           │
      ┌────────────────────┼────────────────────┐
      ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌───────────────────┐
│ CodeReviewer │    │   Explainer  │    │  Code Generator   │
│    Agent     │    │    Agent     │    │       Agent       │
└──────────────┘    └──────────────┘    └───────────────────┘
      │                    │                    │
      └────────────────────┼────────────────────┘
                           │
                           ▼
      ┌─────────────────────────────────────────┐
      │ Smart Tree AST + RAG Engine             │
      │ (Sentence-Transformers: MiniLM-L6-v2)   │
      └────────────────────┬────────────────────┘
                           │
                           ▼
      ┌─────────────────────────────────────────┐
      │ Local Ollama Inference (Private Engine) │
      └─────────────────────────────────────────┘
Specialized Agentic Power
Code Reviewer: Scans for anti-patterns, edge cases, and performance bottlenecks.

Explainer: Walks through complex functions and structural logic in simple terms.

Generator: Drafts clean, typed, production-ready code blocks tailored to your project.

Context Indexing & Retrieval
Smart Tree Mapping: Traverses repository directories while skipping clutter (node_modules, .git, build outputs) to map project layout accurately.

Hybrid Retrieval (Dense + Sparse Search): Combines Vector Semantic Search (sentence-transformers via all-MiniLM-L6-v2) with BM25 Keyword Search (rank-bm25) for exact class, function, or variable matching.

Unified Git Patch Agents: Outputs standard .patch files instead of raw markdown blocks, allowing ai-fix to apply code changes directly via git apply.

🚀 Recent Architecture & Feature Iterations
⚡ Phase 1: Performance & Caching (Engine Scalability)
Incremental File Hashing: Computes MD5/SHA256 hashes during tree traversal to skip unchanged files and avoid redundant embedding generation.

Persistent Local Vector Cache: Stores vector embeddings locally (.codemaster/cache.db) for instant startup times on repeat queries.

Batch Embedding Pipeline: Processes code chunks in async batches to leverage multi-core CPU capabilities.

🧪 Phase 2: Test Suite Hardening & Mocking
Ollama HTTP Client Mocking: Utilizes httpx and respx to test LLM generation offline, simulating slow connections, socket timeouts, and malformed JSON streams.

Coverage Boost: Expanded test coverage across core generation and Ollama orchestration services.

CLI Integration Tests: Added automated execution tests for ai-generate and ai-fix scripts.

🧠 Phase 3: High-Precision Context & Git Patch Agents
Hybrid Search Integration: Merged vector search with BM25 keyword matching to accurately target specific code identifiers.

Direct Patch Application: Implemented patch generation workflows to safely apply automated adjustments directly to local file structures.

🔒 Security & Resilience
Zero External Data Leakage: Local LLM orchestration keeps code strictly on your machine.

Defensive Output Parsing: Sanitizes raw LLM responses and handles non-dictionary returns gracefully to prevent API failures.

App State Verification: Health routes verify server initialization (app.state.activated) prior to processing generation requests.

🧪 Test Suite & Quality
Status: 🟢 20/20 Unit & Integration Tests Passing (Validated across Python 3.10 and 3.11 via GitHub Actions CI/CD)

Test Stack: pytest + pytest-cov + respx

Bash
# Run tests locally
PYTHONPATH=.:backend:backend/app pytest -v

# Run tests with coverage output
pytest --cov=backend/app tests/
🧰 Tech Stack
Domain	Technology
Language & Runtime	Python 3.12
API Framework	FastAPI + Pydantic (V2)
Local LLM Engine	Ollama
Vector Search / RAG	Sentence-Transformers (all-MiniLM-L6-v2) + BM25 (rank-bm25)
CLI & Automation	PowerShell 7 native scripts (ai-generate, ai-fix)
Containerization	Docker Desktop
Testing	Pytest, Pytest-Cov, Respx
⚡ Quickstart
Prerequisites
Ollama installed and running locally

Docker Desktop (optional, if running containerized)

Python 3.12+

1. Clone & Set Up
Bash
git clone https://github.com/sharfuddin18/codemaster-ai.git
cd codemaster-ai

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt
2. Configure Environment
Set environment variables to point to your local Ollama setup:

Bash
export LLM_PROVIDER=ollama
export OLLAMA_ENABLED=true
export OLLAMA_BASE_URL=http://localhost:11434
3. Run Backend Server
Bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
Interactive API documentation will be available at http://localhost:8000/docs.

💻 Usage Examples
Option 1: API Endpoint (Curl)
Bash
curl -X POST http://localhost:8000/generate-code \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write an async Python function to calculate Fibonacci numbers with memoization"
  }'
Option 2: CLI Native Helpers
PowerShell
# Fast terminal code generation
ai-generate -Prompt "Create a FastAPI route for user authentication"

# Instant terminal code fix
ai-fix -File "./backend/app/routes/generation.py"
🤝 Let's Connect
I’m actively iterating on Codemaster-AI to make it faster, smarter, and seamlessly integrated with local workflows. If you have ideas for new specialized agents, context improvements, or bug reports, feel free to open an issue or submit a Pull Request.

Author: Sharfuddin Ahmed (@sharfuddin18)

License: MIT License
