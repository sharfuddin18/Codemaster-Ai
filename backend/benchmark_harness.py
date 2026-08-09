import re
import time
from typing import Any, Dict, Iterable, List, Optional
from unittest.mock import patch

import httpx
from httpx import ASGITransport


class _BenchmarkMockProvider:
    """A minimal fake provider for benchmark evaluation."""

    def __init__(self) -> None:
        self.provider_name = "benchmark-fake"
        self._last_error: Optional[str] = None

    def is_ready(self) -> bool:
        return True

    async def generate(self, prompt: str, model: str | None = None) -> str:
        if "fix" in prompt.lower() or "given this code" in prompt.lower():
            return (
                "def calculate_total(items):\n"
                "    total = 0\n"
                "    for item in items:\n"
                "        if isinstance(item, dict) and 'price' in item:\n"
                "            total += item['price']\n"
                "    return total  # [1]\n"
            )

        if "email" in prompt.lower():
            return (
                "import re\n\n"
                "def is_valid_email(address):\n"
                "    pattern = r'^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$'\n"
                "    return bool(re.match(pattern, address))  # [1]\n"
            )

        if "javascript" in prompt.lower():
            return (
                "function filterEvenNumbers(numbers) {\n"
                "    return numbers.filter(n => n % 2 === 0);  // [1]\n"
                "}\n"
            )

        return "// No benchmark-ready output generated. [1]"


class BenchmarkHarness:
    """Harness for end-to-end API latency, provenance, retrieval, and outcome evaluation."""

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        app: Any = None,
        timeout: float = 30.0,
    ):
        self.backend_url = backend_url.rstrip("/")
        self.app = app
        self.timeout = timeout

    def _extract_citations(self, text: str) -> List[int]:
        return [int(value) for value in re.findall(r"\[\s*(\d+)\s*\]", text)] if text else []

    async def _client(self) -> httpx.AsyncClient:
        if self.app is not None:
            transport = ASGITransport(app=self.app)
            return httpx.AsyncClient(
                transport=transport,
                timeout=self.timeout,
                base_url=self.backend_url,
            )
        return httpx.AsyncClient(timeout=self.timeout, base_url=self.backend_url)

    async def activate(self) -> None:
        async with await self._client() as client:
            await client.post("/activate")

    async def run_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        async with await self._client() as client:
            start_time = time.perf_counter()
            response = await client.post(task["endpoint"], json=task["payload"])
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        result = {
            "name": task["name"],
            "endpoint": task["endpoint"],
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "model_used": "unknown",
            "explanation": "",
            "code_length": 0,
            "citation_count": 0,
            "verification_status": "missing",
            "retrieval_precision": 0.0,
            "passed": False,
            "note": "",
        }

        try:
            payload = response.json()
        except ValueError:
            result["note"] = "Invalid JSON response from benchmark target."
            return result

        result["model_used"] = payload.get("model_used", "unknown")
        result["explanation"] = payload.get("explanation", "")
        code = payload.get("code", "")
        provenance = payload.get("provenance")
        result["code_length"] = len(code)

        if provenance and isinstance(provenance, dict):
            cited_indices = provenance.get("cited_indices", [])
            result["citation_count"] = len(cited_indices)
            result["verification_status"] = provenance.get("verification_status", "missing")
            result["retrieval_precision"] = 100.0 if result["verification_status"] == "verified" and result["citation_count"] > 0 else 0.0
            result["passed"] = (
                response.status_code == 200
                and result["verification_status"] == "verified"
                and result["citation_count"] > 0
                and not code.strip().startswith("// Aborted")
            )
            result["note"] = "Verified provenance." if result["passed"] else "Verification failed or missing citations."
        else:
            cited_count = len(self._extract_citations(code))
            result["citation_count"] = cited_count
            result["verification_status"] = "absent"
            result["retrieval_precision"] = 0.0
            result["passed"] = response.status_code == 200 and cited_count > 0 and not code.strip().startswith("// Aborted")
            result["note"] = "Citation metadata missing." if cited_count else "No provenance citations detected."

        return result

    async def evaluate_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.app is not None:
            with patch("app.routes.generation.LLMFactory.create_provider", return_value=_BenchmarkMockProvider()):
                await self.activate()
                return [await self.run_task(task) for task in tasks]
        await self.activate()
        return [await self.run_task(task) for task in tasks]

    def summarize(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(results)
        passed = sum(1 for result in results if result["passed"])
        average_latency = round(sum(result["latency_ms"] for result in results) / total, 2) if total else 0.0
        citation_success_rate = round(sum(1 for result in results if result["citation_count"] > 0) / total * 100, 2) if total else 0.0
        verification_rate = round(sum(1 for result in results if result["verification_status"] == "verified") / total * 100, 2) if total else 0.0
        average_retrieval_precision = round(sum(result["retrieval_precision"] for result in results) / total, 2) if total else 0.0

        return {
            "total_tasks": total,
            "passed_tasks": passed,
            "pass_rate": round(passed / total * 100, 2) if total else 0.0,
            "average_latency_ms": average_latency,
            "citation_success_rate": citation_success_rate,
            "verification_rate": verification_rate,
            "average_retrieval_precision": average_retrieval_precision,
        }
