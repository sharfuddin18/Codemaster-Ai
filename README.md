# Codemaster-AI 🚀

> A privacy-first, agent-driven local AI coding engine designed to live inside your terminal, index your entire codebase, and handle real-world development tasks without sending your code to external servers.

Built with ☕ and late-night persistence by **Sharfuddin Ahmed** ([@sharfuddin18](https://github.com/sharfuddin18)) — self-taught vibe coder, builder, and self-deploying dev.

---

## 💡 Why I Built This

I got tired of AI coding assistants that feel like basic API wrappers around third-party endpoints. I needed something that:
1. **Lives in my terminal** — I hate switching windows to copy-paste code snippets.
2. **Respects code privacy** — Everything runs 100% locally on my hardware via Ollama.
3. **Understands full-project context** — It doesn't just read a single active file; it maps project relationships so it doesn't hallucinate missing imports or broken signatures.

Whether I'm debugging a stubborn script or scaffolding a new backend feature, **Codemaster-AI** works *with* my workflow rather than interrupting it.

---

## 🏗️ Architecture & How It Works

Instead of dumping massive raw files into a single context window, Codemaster-AI breaks down code parsing into dedicated modular pipelines:

```text
               ┌────────────────────────┐
               │    Terminal / CLI      │
               │ (ai-generate / ai-fix) │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │    FastAPI Backend     │
               └───────────┬────────────┘
                           │
      ┌────────────────────┼────────────────────┐
      ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌───────────────────┐
│ CodeReviewer │   │   Explainer  │   │  Code Generator   │
│    Agent     │   │    Agent     │   │      Agent        │
└──────────────┘   └──────────────┘   └───────────────────┘
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
1. Specialized Agentic PowerInstead of relying on one generic prompt, tasks are routed to specialized agents:Code Reviewer: Scans for anti-patterns, edge cases, and performance bottlenecks.Explainer: Walks through complex functions and structural logic in simple terms.Generator: Drafts clean, typed, production-ready code blocks tailored to your project.2. Context Indexing (Smart Tree + RAG)Smart Tree Mapping: Traverses repository directories while skipping heavy clutter (node_modules, .git, build outputs) to build an accurate layout of your project structure.Vector Semantic Search: Uses sentence-transformers (all-MiniLM-L6-v2) to turn function definitions, docstrings, and modules into vector embeddings. When you ask a question, RAG pulls only the exact context required.3. Native CLI ScriptsFeatures custom terminal utilities like ai-generate and ai-fix powered by PowerShell 7 automation, allowing you to run generation tasks directly from command-line workflows.🔒 Security & ResilienceZero External Data Leakage: Powered by local LLM orchestration via Ollama. Your codebase stays strictly on your local machine.Defensive Output Parsing: Backend parsers safely sanitize raw LLM outputs, gracefully falling back on non-dict returns to prevent API crashes.App State Verification: Health routes explicitly check server initialization (app.state.activated) before serving generation requests.🧪 Test Suite & QualityI treat test coverage as a priority, not an afterthought. The core utility helpers and API routes are covered by unit test cases.Status: 🟢 11/11 Unit Tests PassingTest Stack: pytest + pytest-covVerified Components:Endpoint health status and app activation stateOllama text extraction and non-dict fallback parsingRequest payload validation across generation routesBash# Run tests locally
pytest -v

# Run tests with coverage output
pytest --cov=backend/app tests/
🧰 Tech StackDomainTechnologyLanguage & RuntimePython 3.12API FrameworkFastAPI + Pydantic (V2)Local LLM EngineOllamaVector Search / RAGSentence-Transformers (all-MiniLM-L6-v2)CLI & AutomationPowerShell 7 native scripts (ai-generate, ai-fix)ContainerizationDocker DesktopTestingPytest, Pytest-Cov⚡ QuickstartPrerequisitesOllama installed and running locallyDocker Desktop (optional, if running containerized)Python 3.12+1. Clone & Set UpBashgit clone [https://github.com/sharfuddin18/codemaster-ai.git](https://github.com/sharfuddin18/codemaster-ai.git)
cd codemaster-ai

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
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
🤝 Let's ConnectI’m actively iterating on Codemaster-AI to make it faster, smarter, and even better integrated with local workflows.If you have ideas for new specialized agents, context improvements, or run into any bugs, feel free to open an issue or submit a Pull Request.Author: Sharfuddin Ahmed (@sharfuddin18)License: MIT License
