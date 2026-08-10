# CodeMaster-AI Architecture

## Overview

CodeMaster-AI is a local-first AI coding assistant built around a Python FastAPI backend, local Ollama inference, hybrid retrieval, specialized coding agents, CLI tooling, and an interactive terminal UI.

The architecture is designed to keep the development workflow close to the user's local environment while providing structured code generation, review, explanation, retrieval, patch generation, and provenance verification.

## High-Level Flow

```text
Terminal / CLI / TUI
        |
        v
FastAPI backend
        |
        +--> Control routes
        +--> Generation routes
        +--> Health routes
        +--> MCP routes
        |
        v
Agent and orchestration layer
        |
        +--> Generator
        +--> Reviewer
        +--> Explainer
        |
        v
Hybrid retrieval
        |
        +--> Dense vector retrieval
        +--> BM25 keyword retrieval
        |
        v
Local Ollama inference
        |
        v
Generated response + provenance verification
```

## Repository Structure

### `backend/`

Contains the primary Python backend and supporting services.

- `app/` - FastAPI application, configuration, models, utilities, and API routes/services.
- `database/` - Persistent application state backed by TinyDB.
- `model_orchestrator.py` - Model orchestration abstraction.
- `provider_manager.py` - Provider management abstraction.
- `session_memory.py` - Session-level memory handling.
- `tui_app.py` - Interactive terminal user interface.
- `tests/` - Backend-focused automated tests.

### `cli_tools/`

Contains command-line helpers for interacting with CodeMaster-AI functionality.

### `tests/`

Contains additional project-level automated tests.

### `.github/`

Contains repository automation, issue templates, Dependabot configuration, and GitHub Actions workflows.

### `data/`

Contains local application data and Ollama-related resources used by the development environment.

## FastAPI Application

The main FastAPI application is defined in `backend/app/main.py`.

The application initializes persisted state, configures request logging and lifecycle handling, and connects the main API to dedicated routers.

The current router structure includes:

- Control functionality
- Code generation functionality
- Health checks
- Model Context Protocol (MCP) functionality

Pydantic models in `backend/app/models.py` define structured request and response data such as code generation requests, fixes, sources, and provenance information.

Phase 3 runtime verification exercised applicable FastAPI/TestClient paths through the real application environment, including request validation, successful generation, retrieval/provider failure handling, and response/error behavior.

## AI and Model Layer

The backend separates model/provider responsibilities from the API layer.

### Model orchestration

`backend/model_orchestrator.py` provides the model orchestration abstraction used to coordinate model operations.

The verified Phase 3 request flow is:

```text
Request
  ↓
Routing
  ↓
Retrieval
  ↓
Context Assembly
  ↓
Agent
  ↓
Provider
  ↓
Response
```

Phase 3 verified routing, retrieval/context handoff, provider selection, response handling, and controlled failure propagation.

### Provider management

`backend/provider_manager.py` provides provider-management functionality so model access is not tightly coupled to individual API routes.

Verified provider behavior includes provider/model selection, availability handling, provider exceptions, malformed/empty responses, and disabled-provider behavior. Local and cloud provider paths remain distinct.

### Ollama

CodeMaster-AI uses Ollama for local LLM inference. This keeps the primary model execution path on the local development environment when configured for Ollama.

Ollama provider behavior and unavailable-provider handling are covered by the available test environment; live Ollama model execution remains environment-dependent and is not claimed as a live Phase 3 verification result.

## Retrieval and Agents

The project uses a hybrid retrieval pipeline combining dense vector retrieval with BM25 keyword ranking.

Phase 3 regression-tested the hybrid ranking path so dense and BM25 signals both participate rather than merely existing as separate retrieval functions. Retrieval validation covers top-k handling, empty/no-result behavior, retrieval metadata/provenance, and controlled retrieval failures.

### Vector persistence and indexing

Phase 3 verified vector-index creation, embedding insertion, similarity search, FAISS persistence/reload, embedding-dimension metadata validation, corrupted/incompatible persistence handling, rebuild behavior, and explicit vector-index failure state.

A reliability defect was corrected where an indexing failure could be logged/skipped and leave a partially built index appearing usable. The vector engine now surfaces the indexing failure rather than incorrectly reporting a successful `READY` state.

### Incremental indexing and cache

The verified incremental indexing model is:

```text
File
 ↓
Hash
 ↓
Previous State
 ↓
Unchanged → Reuse / Skip
Changed   → Reprocess
Deleted   → Invalidate
New       → Process
```

Phase 3 verified unchanged-file reuse, changed/deleted-file invalidation, cache persistence/reload, stale-context prevention, and index/cache consistency.

The architecture also includes specialized coding agents for:

- Code generation
- Code review
- Code explanation

This separation allows retrieval and model orchestration to support different coding tasks without placing all responsibilities inside the HTTP layer.

## MCP Runtime Boundary

The MCP capabilities and `retrieve`, `generate`, and `fix` routes were exercised through runtime tests. Coverage includes request validation, controlled retrieval/provider failures, and response structure rather than route inspection alone.

## Provenance and Verification

Generated responses can include provenance and source information. The project contains dedicated provenance-verification tests and models for representing sources and provenance data.

The goal is to make generated results easier to inspect and validate rather than treating model output as inherently trustworthy.

Phase 3 routes generation context through hybrid retrieval and preserves retrieval metadata/provenance for response verification.

## Persistence and Session State

`backend/database/db.py` provides application state persistence through TinyDB.

`backend/session_memory.py` provides session-level memory handling for conversational or task-oriented workflows.

The FastAPI application loads persisted state during startup and performs cleanup during shutdown.

## CLI and Terminal UI

CodeMaster-AI provides multiple interaction surfaces:

- CLI helper scripts under `cli_tools/`
- `run_tui.py` for the interactive terminal interface
- REST endpoints exposed by the FastAPI backend

The TUI is implemented using Textual and Rich and provides terminal-oriented views for coding workflows and provenance information.

## Patch-Based Workflow

The project supports patch-based fixes that produce `.patch` files suitable for applying with Git. This provides a safer workflow for reviewing generated changes before applying them to a working tree.

Phase 3 verified valid and malformed patch handling, invalid and unsafe paths, path traversal protection, patch conflicts/failures, successful application, and post-application verification. Unsafe paths are rejected before patch application.

## Failure Propagation and Reliability

Phase 3 reviewed relevant retrieval, vector, cache, provider, agent, MCP, FastAPI, and patch paths for silent-failure patterns. Cases where genuine infrastructure failures could otherwise appear successful were corrected. This does not claim that every generic exception or fallback pattern was removed.

## Testing

The repository contains backend and project-level tests covering areas including:

- Application structure
- Code generation
- Helper utilities
- MCP functionality
- Ollama services
- Persistent state
- Agents
- Provenance verification
- Vector retrieval
- Cache behavior
- Hybrid ranking
- Vector persistence/reload and failure behavior
- Provider behavior
- Patch validation

Phase 3 final verification recorded `57` passing tests, Python 3.10 CI pass, Python 3.11 CI pass, Flake8 pass, and CodeQL pass. `pip check` also passed in the final verification environment.

The BM25 regression fixture was corrected after the initial test exposed that its corpus was too small for the intended IDF distinction; an unrelated document was added while preserving the intended assertion.

A known non-blocking Starlette/httpx TestClient deprecation warning remains under FastAPI `0.141.1`, Starlette `1.6.0`, and httpx `0.28.1`. The warning does not currently fail the test suite, and no speculative dependency upgrade was performed.

Tests should be run before submitting changes so that documentation, tooling, and application changes can be validated independently.

## Configuration

Backend configuration is managed through the application configuration layer in `backend/app/config.py`.

The repository also provides `backend/.env.example` for documenting expected environment configuration. Secrets and local credentials should not be committed.

## Development and Deployment

Local development can run the FastAPI backend with Uvicorn. The repository also contains Docker configuration for backend services.

GitHub Actions workflows under `.github/workflows/` provide repository automation. Production deployment configuration should be treated separately from local development changes.

## Design Principles

The architecture follows several practical principles:

1. Keep model execution local when possible.
2. Separate API routing from model/provider orchestration.
3. Combine semantic and keyword retrieval.
4. Make generated changes reviewable through patch-based workflows.
5. Preserve provenance information where available.
6. Keep automated tests alongside the components they validate.
7. Avoid coupling development tooling directly to production deployment.
8. Surface genuine infrastructure failures rather than presenting partial state as successful.
9. Keep incremental index and cache state consistent with repository changes.

## Related Documentation

- `README.md` - Project overview and quickstart.
- `CONTRIBUTING.md` - Contribution workflow and review guidelines.
- `SECURITY.md` - Security guidance.
- `CODE_OF_CONDUCT.md` - Community standards.
