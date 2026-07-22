🚀 CodeMaster AI
Context-aware local AI coding assistant designed to digest real-world codebases, map full project trees, and deliver hyper-relevant code generation.

Built and maintained by Sharfuddin — a self-taught vibe coder, builder, and self-deploying developer.

💡 Why CodeMaster AI?
Most AI coding tools struggle when you drop them into a massive, multi-file codebase. They either lose track of imports, hallucinate function signatures, or burn through token limits trying to read files they don't need.

CodeMaster AI solves this by pairing local LLM inference with intelligent codebase indexing. Instead of dumping raw files into a prompt, it maps your project, pulls only relevant context via vector search, and hands the LLM a clean, structured view of your software architecture.

🛠️ How It Works & Key Architecture
Plaintext
[ User Prompt / Code Request ]
            │
            ▼
   ┌─────────────────┐
   │   Smart Tree    │ ──► Traverses repo & builds context graph
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Vector + RAG    │ ──► Fetches relevant snippets via semantic search
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ FastAPI Backend │ ──► Validates request state & structures payload
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Ollama Pipeline │ ──► Runs inference locally (Fast & Private)
   └─────────────────┘
1. Smart Tree AST & Context Mapping
Reads your project structure dynamically without choking on bloated node_modules, .git, or build outputs.

Maps module dependencies and file relationships so the AI understands where a function lives and what depends on it.

2. RAG & Vector Embeddings
Converts code blocks, function definitions, and docstrings into dense vector representations.

Uses Retrieval-Augmented Generation (RAG) to pull only the exact code snippets needed for a prompt, keeping context windows lightweight and fast.

3. Ollama Service Integration
Powered by local LLM orchestration using Ollama.

Zero external API vendor lock-in for core generation — keep your code local, private, and fast.

4. Robust FastAPI Core
Built on an asynchronous Python/FastAPI backend (backend/app).

Strict health check assertions, input sanitization, and fallback parsing for raw LLM outputs.

🔒 Security & Safety First
Local-First Processing: Code context can run fully on-device via Ollama, preventing proprietary codebase leaks to third-party endpoints.

Sanitized Parser Pipeline: Defensive response parsing handles malformed LLM outputs and JSON non-dict fallbacks without crashing the server.

Explicit App State Management: Health routes require explicit activation verification (app.state.activated) to ensure backend services are initialized before serving traffic.

🧪 Testing & Quality Assurance
I treat test coverage as a first-class feature. Every route, helper function, and fallback condition is regularly verified against edge cases.

Status: 🟢 11/11 Unit Tests Passing

Test Framework: pytest + pytest-cov

Current Coverage Highlights:

Health & App Lifecycle: backend/app/routes/health.py (Fully verified)

Helper Utilities: test_helpers.py (Validates non-dict fallback parsing & text extraction)

Generation Endpoints: test_generation.py (Validates payload structure and app state handling)

Bash
# Run the test suite locally
pytest -v

# Run with coverage report
pytest --cov=backend/app tests/
🧰 Tech Stack
Layer	Technology
Language	Python 3.11+
Backend API	FastAPI, Uvicorn
Inference Engine	Ollama
Vector Indexing & RAG	Vector Embeddings + Smart Tree AST Parser
Testing & CI	Pytest, Pytest-Cov, GitHub Actions
⚡ Quickstart
1. Prerequisites
Python 3.11+

Ollama installed and running locally

2. Clone & Setup
Bash
# Clone the repository
git clone https://github.com/your-username/codemaster-ai.git
cd codemaster-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
3. Environment Configuration
Create a .env file in the root directory:

Code snippet
APP_ENV=development
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=qwen2.5-coder # or your preferred local model
4. Launch the Server
Bash
# Start backend server
uvicorn backend.app.main:app --reload
Server will start on [http://127.0.0.1:8000](http://127.0.0.1:8000) with interactive docs available at /docs.

📌 Project Roadmap
[x] Core FastAPI backend setup & health monitoring

[x] Ollama service integration with response extraction helpers

[x] Smart Tree context generator

[x] Full unit testing suite for helpers & generation routes (PR #42 merged)

[ ] Boost unit test coverage on generation.py and ollama_service.py (>80%)

[ ] Add caching layer for frequent vector lookup queries

Built with ☕ and persistence by Sharfuddin. Feel free to open an issue or submit a PR!
