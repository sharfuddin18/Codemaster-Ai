import time
import asyncio
from typing import Dict, Any, List
from tabulate import tabulate

class BenchmarkHarness:
    """
    Harness to evaluate First Token Latency (TTFT), Tokens Per Second (TPS),
    and RAG Context Retrieval Precision.
    """
    def __init__(self, model_name: str = "qwen2.5-coder"):
        self.model_name = model_name

    async def run_benchmark(self, prompt: str, rag_context: str = None) -> Dict[str, Any]:
        """
        Simulates model inference and measures execution metrics.
        """
        start_time = time.perf_counter()
        first_token_time = None
        tokens_generated = 0

        # Build prompt with or without RAG context
        full_prompt = f"Context: {rag_context}\n\nPrompt: {prompt}" if rag_context else prompt

        # Simulated streaming response logic
        simulated_response = (
            f"// Benchmark execution for {self.model_name}\n"
            "def benchmark_target():\n"
            "    return {'status': 'success', 'metric_pass': True}\n"
        )
        words = simulated_response.split(" ")

        for idx, word in enumerate(words):
            if idx == 0:
                await asyncio.sleep(0.12)  # Simulate TTFT delay
                first_token_time = time.perf_counter()
            else:
                await asyncio.sleep(0.03)  # Simulate token generation delay
            tokens_generated += 1

        end_time = time.perf_counter()

        ttft = (first_token_time - start_time) * 1000 if first_token_time else 0  # in ms
        total_duration = end_time - start_time
        tps = tokens_generated / total_duration if total_duration > 0 else 0

        # Calculate simulated retrieval precision if RAG was used
        retrieval_precision = 0.95 if rag_context else 0.0

        return {
            "mode": "RAG-Injected" if rag_context else "Raw Inference",
            "ttft_ms": round(ttft, 2),
            "tps": round(tps, 2),
            "total_tokens": tokens_generated,
            "total_time_s": round(total_duration, 2),
            "retrieval_precision": f"{int(retrieval_precision * 100)}%"
        }

    async def compare_runs(self, prompt: str, context: str) -> str:
        """
        Runs both Raw Inference and RAG-Injected benchmarks and formats a comparison table.
        """
        raw_results = await self.run_benchmark(prompt, rag_context=None)
        rag_results = await self.run_benchmark(prompt, rag_context=context)

        table_data = [
            [
                res["mode"],
                f"{res['ttft_ms']} ms",
                f"{res['tps']} tok/s",
                res["total_tokens"],
                f"{res['total_time_s']} s",
                res["retrieval_precision"]
            ]
            for res in [raw_results, rag_results]
        ]

        headers = ["Mode", "TTFT", "TPS", "Tokens", "Total Time", "RAG Precision"]
        return tabulate(table_data, headers=headers, tablefmt="github")
