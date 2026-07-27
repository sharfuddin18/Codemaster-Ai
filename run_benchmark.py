import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.benchmark_harness import BenchmarkHarness

async def main():
    print("🚀 Running Codemaster-AI Performance & Retrieval Benchmark...\n")
    harness = BenchmarkHarness(model_name="qwen2.5-coder")

    sample_prompt = "Optimize the workspace file indexing algorithm."
    sample_context = "backend/model_orchestrator.py contains workspace file traversal logic."

    report = await harness.compare_runs(sample_prompt, sample_context)
    print(report)
    print("\n✅ Benchmark execution complete!")

if __name__ == "__main__":
    asyncio.run(main())
