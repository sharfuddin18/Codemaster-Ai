# Adding a new LLM provider

To add a new provider to the backend:

1. Create a new provider module under `app/llm/providers/`.
2. Implement the `BaseLLMProvider` interface from `app/llm/providers/base.py`.
   - `generate(prompt: str, model: str | None = None) -> str`
   - `is_ready() -> bool`
   - `get_status() -> dict`
3. Import the new provider class in `app/llm/factory.py`.
4. Register it in the `LLMFactory._registry` mapping.
5. Confirm your `get_status()` payload is JSON-serializable so the health route can return it directly.
6. Add or update a test so the new provider instantiates correctly through the factory.

This keeps the architecture provider-agnostic and makes health checks and generation paths consistent.
