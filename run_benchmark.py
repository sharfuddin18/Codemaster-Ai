import asyncio
import sys
import os

workspace_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, workspace_root)
sys.path.insert(0, os.path.join(workspace_root, "backend"))
sys.path.insert(0, os.path.join(workspace_root, "backend", "app"))

from backend.benchmark_harness import BenchmarkHarness
from backend.app.main import app as backend_app
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

SAMPLE_TASKS = [
    {
        "name": "Generate Python helper",
        "endpoint": "/generate-code",
        "payload": {
            "prompt": "Write a Python function that validates email addresses using regex and returns a boolean.",
            "language": "python"
        },
    },
    {
        "name": "Fix function bug",
        "endpoint": "/fix-code",
        "payload": {
            "file_code": "def calculate_total(items):\n    total = 0\n    for item in items:\n        total += item['price']\n    return total\n",
            "instructions": "Fix potential missing key access and guard against non-dictionary items."
        },
    },
    {
        "name": "Generate JavaScript utility",
        "endpoint": "/generate-code",
        "payload": {
            "prompt": "Create a JavaScript function that filters an array of numbers returning only even values.",
            "language": "javascript"
        },
    },
]

async def main():
    console.print(Panel("🚀 Codemaster-AI End-to-End Benchmark & Evaluation Suite", style="bold blue"))

    backend_url = os.getenv("CODEMASTER_AI_BACKEND", "http://testserver")
    harness = BenchmarkHarness(backend_url=backend_url, app=backend_app)

    console.print(f"Using backend: [bold]{backend_url}[/bold] (ASGI app)\n")
    results = await harness.evaluate_tasks(SAMPLE_TASKS)
    summary = harness.summarize(results)

    table = Table(title="Benchmark Task Results", show_lines=True)
    table.add_column("Task", style="bold white")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Latency (ms)", justify="right")
    table.add_column("Passed", justify="center")
    table.add_column("Citations", justify="right")
    table.add_column("Verification", justify="center")
    table.add_column("Note", style="yellow")

    for result in results:
        table.add_row(
            result["name"],
            result["endpoint"],
            str(result["latency_ms"]),
            "✅" if result["passed"] else "❌",
            str(result["citation_count"]),
            result["verification_status"],
            result["note"],
        )

    console.print(table)

    summary_panel = Panel(
        f"Total tasks: {summary['total_tasks']}\n"
        f"Passed: {summary['passed_tasks']} ({summary['pass_rate']}%)\n"
        f"Average latency: {summary['average_latency_ms']} ms\n"
        f"Citation success: {summary['citation_success_rate']}%\n"
        f"Verification rate: {summary['verification_rate']}%\n"
        f"Average retrieval precision: {summary['average_retrieval_precision']}%",
        title="Benchmark Summary",
        style="bold green",
    )

    console.print(summary_panel)
    console.print("\n✅ Benchmark execution complete!\n")

if __name__ == "__main__":
    asyncio.run(main())
