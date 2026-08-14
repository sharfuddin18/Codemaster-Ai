import json
import tempfile
import unittest
from pathlib import Path

from phase4_benchmark import (
    BenchmarkCase,
    BenchmarkRun,
    InferenceResult,
    aggregate,
    calculate_tps,
    load_cases,
    load_run,
    paired_comparison,
    retrieval_precision,
    run_ollama,
    save_run,
)


class Phase4MetricTests(unittest.TestCase):
    def test_tps_uses_eval_metadata(self):
        self.assertEqual(calculate_tps(100, 2_000_000_000), 50.0)

    def test_tps_rejects_invalid_data(self):
        self.assertIsNone(calculate_tps(0, 0))
        self.assertIsNone(calculate_tps("100", 2_000_000_000))

    def test_retrieval_precision_is_source_intersection(self):
        self.assertEqual(retrieval_precision(["a.py", "b.py"], ["b.py", "c.py"]), 0.5)
        self.assertEqual(retrieval_precision([], ["a.py"]), 0.0)

    def test_aggregate_handles_missing_metrics(self):
        rows = [
            InferenceResult("a", "raw_ollama", "m", "a", "t", True, 10, 20, 30),
            InferenceResult("b", "raw_ollama", "m", "b", "t", False, None, None, None),
            InferenceResult("a", "codemaster_rag", "m", "a", "t", True, 20, 10, 40, retrieval_precision=1.0),
        ]
        report = aggregate(rows)
        self.assertEqual(report["raw_ollama"]["cases"], 2)
        self.assertEqual(report["raw_ollama"]["success_rate"], 0.5)
        self.assertEqual(report["codemaster_rag"]["average_retrieval_precision"], 1.0)

    def test_paired_comparison(self):
        rows = [
            InferenceResult("a", "raw_ollama", "m", "a", "t", True, 10, 20, 30),
            InferenceResult("a", "codemaster_rag", "m", "a", "t", True, 15, 25, 40, retrieval_precision=1.0),
        ]
        comparison = paired_comparison(rows)
        self.assertEqual(comparison["paired_case_count"], 1)
        self.assertEqual(comparison["cases"][0]["ttft_delta_ms_rag_minus_baseline"], 5)

    def test_unavailable_ollama_is_controlled_failure(self):
        case = BenchmarkCase("x", "task", ("a.py",))
        result = run_ollama("task", "model", "http://127.0.0.1:1", 0.1, case, "raw_ollama", [])
        self.assertFalse(result.success)
        self.assertIsNone(result.ttft_ms)
        self.assertIsNotNone(result.error)

    def test_result_persistence_round_trip_and_malformed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            run = BenchmarkRun(
                "1.0",
                "id",
                {"model": "m"},
                [InferenceResult("a", "raw_ollama", "m", "a", "t", True, 1, 2, 3)],
                {"raw_ollama": {"cases": 1}},
            )
            save_run(run, path)
            loaded = load_run(path)
            self.assertEqual(loaded.run_id, "id")
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_run(path)

    def test_case_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(
                json.dumps([{"case_id": "x", "task": "task", "expected_sources": ["a.py"]}]),
                encoding="utf-8",
            )
            cases = load_cases(path)
            self.assertEqual(cases, [BenchmarkCase("x", "task", ("a.py",))])


if __name__ == "__main__":
    unittest.main()
