Codemaster-AI 🚀A privacy-first, agent-driven local AI coding engine designed to live inside your terminal, index your entire codebase, and handle real-world development tasks without sending your code to external servers.Built with ☕ and late-night persistence by Sharfuddin Ahmed (@sharfuddin18) — self-taught vibe coder, builder, and self-deploying dev.💡 Why I Built ThisI got tired of AI coding assistants that feel like basic API wrappers around third-party endpoints. I needed something that:Lives in my terminal — I hate switching windows to copy-paste code snippets.Respects code privacy — Everything runs 100% locally on my hardware via Ollama.Understands full-project context — It doesn't just read a single active file; it maps project relationships so it doesn't hallucinate missing imports or broken signatures.Whether I'm debugging a stubborn script or scaffolding a new backend feature, Codemaster-AI works with my workflow rather than interrupting it.🏗️ Architecture & How It WorksInstead of dumping massive raw files into a single context window, Codemaster-AI breaks down code parsing into dedicated modular pipelines:Plaintext               ┌────────────────────────┐
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
Specialized Agentic PowerInstead of relying on one generic prompt, tasks are routed to specialized agents:Code Reviewer: Scans for anti-patterns, edge cases, and performance bottlenecks.Explainer: Walks through complex functions and structural logic in simple terms.Generator: Drafts clean, typed, production-ready code blocks tailored to your project.Context Indexing (Smart Tree + RAG + Hybrid Search)Smart Tree Mapping: Traverses repository directories while skipping heavy clutter (node_modules, .git, build outputs) to build an accurate layout of your project structure.Hybrid Retrieval (Dense + Sparse Search): Combines Vector Semantic Search (sentence-transformers via all-MiniLM-L6-v2) with BM25 Keyword Search (rank-bm25) for exact class, function, or variable name matching. This drastically reduces missing imports and incorrect function signatures.Unified Git Patch AgentsInstead of only returning standard markdown code blocks, the generator agent can output standard .patch files.Allows ai-fix and backend tasks to apply code changes cleanly and directly to your local working directory via git apply.Native CLI ScriptsFeatures custom terminal utilities like ai-generate and ai-fix powered by PowerShell 7 automation, allowing you to run generation tasks directly from command-line workflows.🔒 Security & ResilienceZero External Data Leakage: Powered by local LLM orchestration via Ollama. Your codebase stays strictly on your local machine.Defensive Output Parsing: Backend parsers safely sanitize raw LLM outputs, gracefully falling back on non-dict returns to prevent API crashes.App State Verification: Health routes explicitly check server initialization (app.state.activated) before serving generation requests.🧪 Test Suite & QualityI treat test coverage as a priority, not an afterthought. The core utility helpers, hybrid retriever, and API routes are covered by unit and integration test cases.Status: 🟢 20/20 Unit & Integration Tests Passing (Validated across Python 3.10 and 3.11 via GitHub Actions CI/CD)Test Stack: pytest + pytest-cov + respxVerified Components:Endpoint health status and persistent app activation stateOllama text extraction and non-dict fallback parsingHybrid retriever dense + sparse matching and fallback behaviorsUnified git patch generation and dry-run applicationIncremental file hashing and caching servicesBash# Run tests locally
PYTHONPATH=.:backend:backend/app pytest -v

# Run tests with coverage output
pytest --cov=backend/app tests/
🚀 Recent Architecture & Feature Iterations⚡ Phase 1: Performance & Caching (Engine Scalability)Incremental File Hashing: Computes MD5/SHA256 hashes for files during tree traversal. If a file hasn't changed since the last run, embedding generation is skipped completely.Persistent Local Vector Cache: Stores vector embeddings in lightweight local storage (.codemaster/cache.db) for instant startup times on repeat queries.Batch Embedding Pipeline: Processes code chunks in async batches rather than sequentially to utilize multi-core CPU capabilities.🧪 Phase 2: Test Suite Hardening & MockingMocking Ollama HTTP Client: Utilizes httpx and respx mocking to test LLM generation routes offline, simulating slow connections, socket timeouts, and malformed JSON streams.Target Coverage Boost: Significantly increased core component coverage across generation and Ollama orchestration services.CLI Integration Tests: Added automated execution tests for ai-generate and ai-fix scripts.🧠 Phase 3: High-Precision Context & Git Patch AgentsHybrid Retrieval (Dense + Sparse Search): Integrated Vector Search with BM25 Keyword Search (rank-bm25) to target exact code identifiers.Unified Git Patch Generator: Enabled patch formatting capabilities so updates can be directly applied via git apply.🧰 Tech StackDomainTechnologyLanguage & RuntimePython 3.12API FrameworkFastAPI + Pydantic (V2)Local LLM EngineOllamaVector Search / RAGSentence-Transformers (all-MiniLM-L6-v2) + BM25 (rank-bm25)CLI & AutomationPowerShell 7 native scripts (ai-generate, ai-fix)ContainerizationDocker DesktopTestingPytest, Pytest-Cov, Respx⚡ QuickstartPrerequisitesOllama installed and running locallyDocker Desktop (optional, if running containerized)Python 3.12+1. Clone & Set UpBashgit clone https://github.com/sharfuddin18/codemaster-ai.git
cd codemaster-ai

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt
2. Configure EnvironmentSet your environment variables to point to your local Ollama setup:Bashexport LLM_PROVIDER=ollama
export OLLAMA_ENABLED=true
export OLLAMA_BASE_URL=http://localhost:11434
3. Run Backend ServerBashcd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
Interactive API documentation will be available at http://localhost:8000/docs.💻 Usage ExamplesOption 1: API Endpoint (Curl)Bashcurl -X POST http://localhost:8000/generate-code \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write an async Python function to calculate Fibonacci numbers with memoization"
  }'
Option 2: CLI Native HelpersPowerShell# Fast terminal code generation
ai-generate -Prompt "Create a FastAPI route for user authentication"

# Instant terminal code fix
ai-fix -File "./backend/app/routes/generation.py"
🤝 Let's ConnectI’m actively iterating on Codemaster-AI to make it faster, smarter, and even better integrated with local workflows. If you have ideas for new specialized agents, context improvements, or run into any bugs, feel free to open an issue or submit a Pull Request.Author: Sharfuddin Ahmed (@sharfuddin18)License: MIT License
