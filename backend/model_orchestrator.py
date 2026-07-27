import os
from typing import AsyncGenerator, Dict, Any

class ModelOrchestrator:
    """
    Manages dynamic model routing, streaming, and fallback execution.
    """
    FAST_MODEL = "qwen2.5-coder"
    HEAVY_MODEL = "deepseek-coder"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "mock-key")

    def select_model(self, task_type: str) -> str:
        """
        Determines the appropriate model based on task complexity.
        """
        if task_type.lower() in ["refactor", "architecture", "audit"]:
            return self.HEAVY_MODEL
        return self.FAST_MODEL

    async def stream_completion(
        self, prompt: str, task_type: str = "completion"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams response tokens from the primary model with automatic fallback.
        """
        primary_model = self.select_model(task_type)
        fallback_model = self.HEAVY_MODEL if primary_model == self.FAST_MODEL else self.FAST_MODEL

        try:
            async for chunk in self._execute_stream(primary_model, prompt):
                yield {"model": primary_model, "token": chunk, "fallback": False}
        except Exception:
            # Fallback path if primary model fails
            yield {
                "model": fallback_model, 
                "token": f"\n[System: {primary_model} failed. Falling back to {fallback_model}...]\n", 
                "fallback": True
            }
            async for chunk in self._execute_stream(fallback_model, prompt):
                yield {"model": fallback_model, "token": chunk, "fallback": True}

    async def _execute_stream(self, model: str, prompt: str) -> AsyncGenerator[str, None]:
        """
        Simulates streaming response tokens from an API endpoint.
        """
        import asyncio
        response_text = f"// Executed via {model}\n" + (
            "def optimize_code(data):\n"
            "    # Refactored pipeline\n"
            "    return [x * 2 for x in data if x > 0]\n"
        )
        for word in response_text.split(" "):
            await asyncio.sleep(0.08)
            yield word + " "
