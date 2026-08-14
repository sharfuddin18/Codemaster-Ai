# Phase 4 — Local Benchmarking & Metrics

Phase 4 adds a controlled benchmark layer for comparing two execution conditions:

1. **Raw Ollama** — the benchmark task is sent to the selected Ollama model without Codemaster repository context.
2. **Codemaster RAG** — the same task is passed through the existing Phase 3 hybrid retrieval path, the retrieved repository context is assembled into the prompt, and the selected Ollama model is invoked.

The benchmark is a measurement tool, not a claim that RAG is faster or better.

## Metrics

### TTFT — Time To First Token

TTFT is measured from the start of the Ollama HTTP request until the first non-empty streamed response chunk is received. It is **not** the total request latency.

### TPS — Tokens Per Second

TPS uses Ollama's authoritative generation metadata:

`eval_count / (eval_duration_ns / 1,000,000,000)`

If Ollama does not provide valid token/timing metadata, TPS is recorded as unavailable rather than fabricated.

### Context Retrieval Precision

Each benchmark case declares expected repository source files. Precision is calculated deterministically as:

`|expected sources ∩ retrieved sources| / |expected sources|`

This is source-file precision, not a semantic relevance score.

## Benchmark cases

The initial controlled cases target repository-aware tasks covering:

- hybrid dense + BM25 ranking;
- vector-index failure state;
- generation/context handoff and retrieval failure behavior;
- Ollama provider runtime behavior.

The cases and expected source labels live in `benchmarks/phase4_cases.json`.

## Reproducibility

Run from the repository root after installing the existing project dependencies:

```bash
python run_phase4_benchmark.py
```

Useful overrides:

```bash
python run_phase4_benchmark.py --model qwen2.5-coder:1.5b --top-k 3 --alpha 0.5 --min-score 0.0
```

The runner records model, Ollama endpoint, retrieval configuration, benchmark cases, measurement methodology, environment metadata, per-case outputs, failures, and aggregate metrics. Results are persisted atomically to `.codemaster/benchmarks/phase4-latest.json` by default and should not be committed.

## Live execution and offline behavior

A real benchmark result is produced only when the runner actually receives a live Ollama response. If Ollama is unavailable, the run records a controlled failure and exits non-zero; the implementation does not substitute mock output for live benchmark results.

The Phase 4 unit tests use deterministic fixtures and an intentionally unavailable localhost endpoint to verify infrastructure and failure handling without presenting those executions as live benchmark data.

## Fair-comparison rules

Baseline and RAG use the same benchmark task, model, generation endpoint, timeout, and Ollama generation configuration. The intended experimental difference is the injected repository context. Warm/cold behavior should be interpreted from the recorded run conditions rather than silently mixing runs.

No benchmark number should be published as a performance guarantee. Small samples should be treated as observations, not statistically general performance claims.
