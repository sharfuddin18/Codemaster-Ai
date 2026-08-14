# CodeMaster-AI Architecture

## Overview

CodeMaster-AI is a local-first AI coding assistant built around a Python FastAPI backend, local Ollama inference, hybrid retrieval, coding workflows, CLI tooling, terminal UI, MCP, patch workflows, and provenance verification.

Phase 5 consolidates production model selection into one authoritative routing path. Provider/model selection is no longer split between a ProviderManager, a simulated ModelOrchestrator, and service-local model rules.

## High-Level Flow

```text
User Request
    |
    v
Task Classifier
    |
    v
Task Complexity
    |
    v
Model Policy
    |
    v
ModelRouter
    |
    v
Structured RoutingDecision
    |
    v
LLMFactory
    |
    v
Ollama provider/model
    |
    v
Response / AgentResult
```

Retrieval remains an independent context subsystem used by generation/fix workflows before the selected provider is invoked:

```text
Request
  |
  +--> Hybrid Retrieval --> Context / Provenance
  |
  +--> Unified Model Routing --> LLMFactory --> Provider
                                      |
                                      v
                                   Response
```

## Repository Structure

### `backend/`

Contains the primary Python backend and supporting services.

- `app/` - FastAPI application, configuration, models, utilities, routes, services, and LLM abstractions.
- `database/` - Persistent application state backed by TinyDB.
- `session_memory.py` - Session-level memory handling.
- `tui_app.py` - Interactive terminal user interface.
- `tests/` - Backend-focused automated tests.

The former `provider_manager.py` and `model_orchestrator.py` production abstractions were retired in Phase 5 because they duplicated or simulated provider/model routing.

### `cli_tools/`

Contains command-line helpers for interacting with CodeMaster-AI functionality.

### `tests/`

Contains additional project-level automated tests.

### `.github/`

Contains repository automation, issue templates, Dependabot configuration, and GitHub Actions workflows.

### `data/`

Contains local application data and Ollama-related development resources.

## FastAPI Application

The main FastAPI application is defined in `backend/app/main.py`.

The application initializes persisted state, configures request logging and lifecycle handling, and connects the main API to dedicated routers for control, generation, health, and MCP functionality.

Pydantic models in `backend/app/models.py` define structured API request and response data such as code generation requests, fixes, sources, and provenance information.

Phase 3 runtime verification exercised applicable FastAPI/TestClient paths through the real application environment, including request validation, generation, retrieval/provider failure handling, and response/error behavior.

## Phase 5 Model and Provider Architecture

### Authoritative routing types

`backend/app/llm/routing.py` defines the production routing vocabulary:

- `TaskType` - high-level coding task category.
- `TaskComplexity` - deterministic complexity classification.
- `AgentRequest` - structured input to the routing system.
- `ModelPolicy` - explicit deterministic model-selection policy.
- `RoutingDecision` - structured provider/model decision.
- `AgentResult` - structured result boundary for agent/model workflows.

### Task classification

`TaskClassifier` is the single production classification path. It determines `TaskType` and `TaskComplexity` instead of allowing FastAPI, MCP, CLI, TUI, or individual services to maintain independent model-selection rules.

### Model policy

`ModelPolicy` centralizes the model-selection behavior that previously lived in `ollama_service.py` and the simulated `ModelOrchestrator`. The Phase 5 policy preserves the repository's existing model names and deterministic routing behavior; it does not invent cloud providers or unsupported model capabilities.

### ModelRouter

`ModelRouter` is the one authoritative production router. It converts an `AgentRequest` into a `RoutingDecision` containing task type, complexity, provider, model, and selection reason.

Production generation/fix flows use:

```text
AgentRequest
    ↓
TaskClassifier
    ↓
TaskComplexity
    ↓
ModelPolicy
    ↓
ModelRouter
    ↓
RoutingDecision
```

### LLMFactory

`backend/app/llm/factory.py` is the single provider-instantiation boundary.

`LLMFactory.create(decision)` consumes the structured `RoutingDecision`, creates the selected provider, and returns the already-selected model name. It does not perform a second business-level routing decision.

The existing `LLMClient` remains a compatibility wrapper around `LLMFactory`; it does not own model selection.

### ProviderManager

`backend/provider_manager.py` was retired in Phase 5. Its provider-selection responsibility duplicated `LLMFactory` and could create a competing production path.

No production caller remains dependent on it.

### ModelOrchestrator

`backend/model_orchestrator.py` was retired in Phase 5. Its implementation simulated streaming output and independently selected between hard-coded models, so retaining it would have created a misleading competing production orchestration path.

Its removal does not remove test mocks/fakes or the actual provider implementations.

### Ollama

`backend/app/llm/providers/ollama.py` is the actual local Ollama provider implementation. It executes a provider/model already selected by the routing layer and does not perform business-level model routing.

`backend/app/services/ollama_service.py` retains only low-level compatibility helpers and a compatibility `select_best_model` facade that delegates to `ModelRouter`. It no longer contains an independent model-selection table.

Live Ollama model execution remains environment-dependent. Tests may mock provider behavior, but no unavailable live execution is presented as a real Ollama result.

## Production Generation Flow

Generation and fix routes now converge on the same architecture:

```text
FastAPI request
    ↓
AgentRequest
    ↓
ModelRouter
    ↓
RoutingDecision
    ↓
LLMFactory
    ↓
Ollama / configured provider
    ↓
Response verification
    ↓
CodeResponse / provenance
```

Retrieval is still performed by the existing Phase 3 hybrid retrieval path and remains responsible for repository context, not provider selection.

## Retrieval and Agents

The project uses a hybrid retrieval pipeline combining dense vector retrieval with BM25 keyword ranking.

Phase 3 regression-tested the hybrid ranking path so dense and BM25 signals both participate. Retrieval validation covers top-k handling, empty/no-result behavior, retrieval metadata/provenance, and controlled retrieval failures.

### Vector persistence and indexing

Phase 3 verified vector-index creation, embedding insertion, similarity search, FAISS persistence/reload, embedding-dimension metadata validation, corrupted/incompatible persistence handling, rebuild behavior, and explicit vector-index failure state.

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

## MCP Runtime Boundary

MCP capabilities and the `retrieve`, `generate`, and `fix` routes are covered by runtime tests. Provider/model selection must converge on the same routing architecture rather than maintaining a separate MCP provider factory.

## Provenance and Verification

Generated responses can include provenance and source information. Dedicated verification tests and models represent sources and provenance data.

The goal is to make generated results inspectable rather than treating successful model execution as proof of correctness.

## CLI and Terminal UI

CodeMaster-AI provides CLI helper scripts, `run_tui.py`, and REST endpoints. The TUI is implemented using Textual and Rich. Where these interfaces request model execution, model-selection responsibility belongs to the same routing/factory architecture rather than an interface-specific provider-selection implementation.

## Patch-Based Workflow

The project supports patch-based fixes that produce `.patch` files suitable for applying with Git. Phase 3 verified valid and malformed patch handling, unsafe paths, path traversal protection, conflicts/failures, successful application, and post-application verification.

## Failure Propagation and Reliability

Phase 3 reviewed relevant retrieval, vector, cache, provider, agent, MCP, FastAPI, and patch paths for silent-failure patterns. Genuine infrastructure failures are surfaced rather than presented as successful partial state.

Phase 5 adds routing-level validation for unsupported providers, empty requests, malformed routing decisions, and deterministic policy behavior.

## Testing

Phase 5 adds dedicated routing coverage for:

- `TaskType` and `TaskComplexity` classification;
- deterministic `ModelPolicy` behavior;
- structured `RoutingDecision` values;
- unsupported provider handling;
- `LLMFactory` integration;
- compatibility delegation from the legacy model-selection facade;
- structured `AgentResult` construction.

The existing backend/project tests remain the regression boundary. Phase 5 does not delete or weaken existing tests and does not require live Ollama execution to validate the routing architecture.

## Configuration

Backend configuration is managed through `backend/app/config.py`.

The repository also provides `backend/.env.example` for expected environment configuration. Secrets and local credentials should not be committed.

## Development and Deployment

Local development can run the FastAPI backend with Uvicorn. Docker configuration is provided for backend services.

GitHub Actions workflows under `.github/workflows/` provide repository automation. Production deployment configuration should be treated separately from local development changes.

## Design Principles

1. Keep model execution local when configured for Ollama.
2. Keep one authoritative production model-routing path.
3. Keep `LLMFactory` as the single provider-instantiation boundary.
4. Separate API routing from model/provider orchestration.
5. Combine semantic and keyword retrieval.
6. Make generated changes reviewable through patch-based workflows.
7. Preserve provenance information where available.
8. Keep automated tests alongside the components they validate.
9. Surface genuine infrastructure failures rather than presenting partial state as successful.
10. Keep incremental index and cache state consistent with repository changes.
