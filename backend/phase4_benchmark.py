"""Phase 4 controlled local benchmark: Raw Ollama vs Codemaster retrieval + Ollama."""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    task: str
    expected_sources: tuple[str, ...]


@dataclass
class InferenceResult:
    benchmark_case: str
    execution_mode: str
    model: str
    prompt_id: str
    timestamp: str
    success: bool
    ttft_ms: float | None
    tps: float | None
    generation_duration_ms: float | None
    retrieved_sources: list[str] = field(default_factory=list)
    expected_sources: list[str] = field(default_factory=list)
    retrieval_precision: float | None = None
    output: str = ""
    error: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    token_count: int | None = None
    raw_timing: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkRun:
    schema_version: str
    run_id: str
    configuration: dict[str, Any]
    results: list[InferenceResult]
    aggregate: dict[str, Any]


CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        "retrieval-hybrid-ranking",
        (
            "Explain how Codemaster-AI combines dense vector retrieval and BM25, "
            "including how the hybrid score is formed."
        ),
        ("backend/app/services/hybrid_retriever.py",),
    ),
    BenchmarkCase(
        "vector-index-failure-state",
        (
            "Explain how the repository vector engine handles indexing failures and "
            "what state it exposes after a failed build."
        ),
        ("backend/app/utils/vector_engine.py",),
    ),
    BenchmarkCase(
        "generation-context-handoff",
        (
            "Explain how the generation route retrieves repository context and passes it "
            "into the model prompt, including the retrieval failure behavior."
        ),
        ("backend/app/routes/generation.py",),
    ),
    BenchmarkCase(
        "ollama-provider-runtime",
        "Explain how the Ollama provider calls the local API, selects its model, and handles provider failures.",
        ("backend/app/llm/providers/ollama.py",),
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_ollama_url(value: str) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme or "http", f"{host}{port}", parsed.path, "", ""))


def safe_environment() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "ollama_base_url": safe_ollama_url(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")),
    }


def retrieval_precision(expected: Sequence[str], retrieved: Sequence[str]) -> float:
    """Return the fraction of retrieved source entries that are relevant."""
    expected_set = {str(x) for x in expected if str(x)}
    retrieved_values = [str(x) for x in retrieved if str(x)]
    if not retrieved_values:
        return 0.0
    return sum(source in expected_set for source in retrieved_values) / len(retrieved_values)


def _number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def calculate_tps(eval_count: Any, eval_duration_ns: Any) -> float | None:
    count = _number(eval_count)
    duration = _number(eval_duration_ns)
    if count is None or duration is None or count < 0 or duration <= 0:
        return None
    return count / (duration / 1_000_000_000)


def paired_comparison(results: Iterable[InferenceResult]) -> dict[str, Any]:
    pairs: dict[str, dict[str, InferenceResult]] = {}
    for result in results:
        pairs.setdefault(result.benchmark_case, {})[result.execution_mode] = result
    comparisons = []
    for case_id in sorted(pairs):
        pair = pairs[case_id]
        baseline = pair.get("raw_ollama")
        rag = pair.get("codemaster_rag")
        if baseline is None or rag is None:
            continue
        comparisons.append({
            "benchmark_case": case_id,
            "baseline_success": baseline.success,
            "rag_success": rag.success,
            "ttft_delta_ms_rag_minus_baseline": (
                rag.ttft_ms - baseline.ttft_ms
                if rag.ttft_ms is not None and baseline.ttft_ms is not None
                else None
            ),
            "tps_delta_rag_minus_baseline": (
                rag.tps - baseline.tps
                if rag.tps is not None and baseline.tps is not None
                else None
            ),
            "retrieval_precision": rag.retrieval_precision,
        })
    return {"cases": comparisons, "paired_case_count": len(comparisons)}


def aggregate(results: Iterable[InferenceResult]) -> dict[str, Any]:
    grouped: dict[str, list[InferenceResult]] = {}
    for result in results:
        grouped.setdefault(result.execution_mode, []).append(result)

    report: dict[str, Any] = {}
    for mode, items in grouped.items():
        ttft = [r.ttft_ms for r in items if r.ttft_ms is not None and r.success]
        tps = [r.tps for r in items if r.tps is not None and r.success]
        precision = [r.retrieval_precision for r in items if r.retrieval_precision is not None]
        report[mode] = {
            "cases": len(items),
            "success_rate": sum(r.success for r in items) / len(items) if items else 0.0,
            "average_ttft_ms": statistics.mean(ttft) if ttft else None,
            "median_ttft_ms": statistics.median(ttft) if ttft else None,
            "average_tps": statistics.mean(tps) if tps else None,
            "median_tps": statistics.median(tps) if tps else None,
            "average_retrieval_precision": statistics.mean(precision) if precision else None,
            "median_retrieval_precision": statistics.median(precision) if precision else None,
        }
    return report


def _post_json_stream(
    url: str,
    payload: dict[str, Any],
    timeout: float,
    on_first_token: Callable[[], None],
) -> tuple[str, dict[str, Any], float, float]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    first_token_time: float | None = None
    output_parts: list[str] = []
    final: dict[str, Any] = {}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                if not raw_line.strip():
                    continue
                item = json.loads(raw_line.decode("utf-8"))
                if item.get("error"):
                    raise RuntimeError(f"Ollama returned an error: {item['error']}")
                chunk = str(item.get("response", ""))
                if chunk and first_token_time is None:
                    first_token_time = time.perf_counter()
                    on_first_token()
                output_parts.append(chunk)
                if item.get("done") is True:
                    final = item
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Ollama connection failed: {exc}") from exc
    end = time.perf_counter()
    if first_token_time is None:
        raise RuntimeError("Ollama returned no generated token")
    return "".join(output_parts), final, (first_token_time - start) * 1000, (end - start) * 1000


def run_ollama(
    prompt: str,
    model: str,
    base_url: str,
    timeout: float,
    case: BenchmarkCase,
    mode: str,
    retrieved: list[str],
) -> InferenceResult:
    payload = {"model": model, "prompt": prompt, "stream": True}
    timestamp = utc_now()
    try:
        output, metadata, ttft_ms, wall_ms = _post_json_stream(
            f"{base_url.rstrip('/')}/api/generate", payload, timeout, lambda: None
        )
        eval_count = _number(metadata.get("eval_count"))
        eval_duration = _number(metadata.get("eval_duration"))
        return InferenceResult(
            benchmark_case=case.case_id,
            execution_mode=mode,
            model=model,
            prompt_id=case.case_id,
            timestamp=timestamp,
            success=bool(output.strip()),
            ttft_ms=ttft_ms,
            tps=calculate_tps(eval_count, eval_duration),
            generation_duration_ms=(eval_duration / 1_000_000) if eval_duration else wall_ms,
            retrieved_sources=retrieved,
            expected_sources=list(case.expected_sources),
            retrieval_precision=(
                retrieval_precision(case.expected_sources, retrieved)
                if mode == "codemaster_rag"
                else None
            ),
            output=output,
            environment=safe_environment(),
            token_count=eval_count,
            raw_timing={
                k: metadata.get(k)
                for k in (
                    "total_duration",
                    "load_duration",
                    "prompt_eval_count",
                    "prompt_eval_duration",
                    "eval_count",
                    "eval_duration",
                )
                if k in metadata
            },
        )
    except Exception as exc:
        return InferenceResult(
            benchmark_case=case.case_id,
            execution_mode=mode,
            model=model,
            prompt_id=case.case_id,
            timestamp=timestamp,
            success=False,
            ttft_ms=None,
            tps=None,
            generation_duration_ms=None,
            retrieved_sources=retrieved,
            expected_sources=list(case.expected_sources),
            retrieval_precision=(
                retrieval_precision(case.expected_sources, retrieved)
                if mode == "codemaster_rag"
                else None
            ),
            environment=safe_environment(),
            error=str(exc),
        )


def raw_prompt(case: BenchmarkCase) -> str:
    return (
        "You are evaluating Codemaster-AI as a coding assistant. "
        "Answer this repository-specific task without being given repository context:\n\n"
        f"{case.task}\n"
    )


def rag_prompt(case: BenchmarkCase, context: Sequence[dict[str, Any]]) -> str:
    formatted = []
    for index, item in enumerate(context, 1):
        formatted.append(f"[{index}] File: {item.get('file', 'unknown')}\n{item.get('text', item.get('snippet', ''))}")
    return (
        "You are evaluating Codemaster-AI as a project-aware coding assistant. "
        "Use only the retrieved repository context when answering.\n\n"
        f"Task:\n{case.task}\n\nRetrieved repository context:\n\n" + "\n\n".join(formatted)
    )


def load_cases(path: Path | None = None) -> list[BenchmarkCase]:
    if path is None:
        default_path = Path(__file__).resolve().parents[1] / "benchmarks" / "phase4_cases.json"
        if default_path.exists():
            path = default_path
        else:
            return list(CASES)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        BenchmarkCase(
            str(item["case_id"]),
            str(item["task"]),
            tuple(str(source) for source in item.get("expected_sources", [])),
        )
        for item in raw
    ]


def retrieve_context(case: BenchmarkCase, top_k: int, alpha: float, min_score: float) -> list[dict[str, Any]]:
    try:
        from backend.app.routes.generation import _parse_retrieval_doc, get_hybrid_retriever
    except Exception as exc:
        raise RuntimeError(f"Codemaster retrieval could not be imported: {exc}") from exc
    results = get_hybrid_retriever().search(case.task, top_k=top_k, alpha=alpha, min_score=min_score)
    return [_parse_retrieval_doc(result) for result in results]


def execute(
    cases: Sequence[BenchmarkCase],
    model: str,
    base_url: str,
    timeout: float,
    top_k: int,
    alpha: float,
    min_score: float,
) -> BenchmarkRun:
    results: list[InferenceResult] = []
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for case in cases:
        baseline = run_ollama(raw_prompt(case), model, base_url, timeout, case, "raw_ollama", [])
        results.append(baseline)
        try:
            context = retrieve_context(case, top_k, alpha, min_score)
            retrieved_sources = sorted({str(item.get("file", "unknown")) for item in context if item.get("file")})
            rag = run_ollama(
                rag_prompt(case, context),
                model,
                base_url,
                timeout,
                case,
                "codemaster_rag",
                retrieved_sources,
            )
        except Exception as exc:
            rag = InferenceResult(
                benchmark_case=case.case_id,
                execution_mode="codemaster_rag",
                model=model,
                prompt_id=case.case_id,
                timestamp=utc_now(),
                success=False,
                ttft_ms=None,
                tps=None,
                generation_duration_ms=None,
                expected_sources=list(case.expected_sources),
                retrieval_precision=0.0,
                environment=safe_environment(),
                error=str(exc),
            )
        results.append(rag)
    config = {
        "model": model,
        "ollama_base_url": safe_ollama_url(base_url),
        "timeout_seconds": timeout,
        "top_k": top_k,
        "alpha": alpha,
        "min_score": min_score,
        "benchmark_cases": [c.case_id for c in cases],
        "measurement": {
            "ttft": "wall-clock elapsed from HTTP request start until first non-empty streamed response chunk",
            "tps": "Ollama eval_count divided by eval_duration in seconds",
            "retrieval_precision": (
                "relevant retrieved source entries divided by retrieved source entries"
            ),
        },
    }
    aggregate_report = aggregate(results)
    aggregate_report["paired_comparison"] = paired_comparison(results)
    return BenchmarkRun("1.0", run_id, config, results, aggregate_report)


def save_run(run: BenchmarkRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(run)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_run(path: Path) -> BenchmarkRun:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        results = [InferenceResult(**item) for item in payload["results"]]
        return BenchmarkRun(
            schema_version=str(payload["schema_version"]),
            run_id=str(payload["run_id"]),
            configuration=dict(payload["configuration"]),
            results=results,
            aggregate=dict(payload["aggregate"]),
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"Malformed Phase 4 benchmark result: {path}") from exc


def print_report(run: BenchmarkRun) -> None:
    print(f"Phase 4 benchmark run: {run.run_id}")
    for mode, metrics in run.aggregate.items():
        print(f"\n{mode}")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
    failed = [r for r in run.results if not r.success]
    if failed:
        print(f"\nFailed cases: {len(failed)}")
        for result in failed:
            print(f"  {result.execution_mode}/{result.benchmark_case}: {result.error}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 4 Raw Ollama vs Codemaster RAG benchmark.")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"))
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".codemaster/benchmarks/phase4-latest.json"))
    args = parser.parse_args(argv)
    if args.top_k < 1 or not 0 <= args.alpha <= 1 or not 0 <= args.min_score <= 1:
        parser.error("top-k must be >= 1; alpha and min-score must be between 0 and 1")
    cases = load_cases(args.cases)
    run = execute(cases, args.model, args.ollama_url, args.timeout, args.top_k, args.alpha, args.min_score)
    save_run(run, args.output)
    print_report(run)
    return 0 if all(r.success for r in run.results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
