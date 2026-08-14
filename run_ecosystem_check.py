import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app.llm.factory import LLMFactory
from backend.app.llm.routing import AgentRequest, route_request
from backend.session_memory import SessionMemory


def main():
    print("🌐 Verifying the Phase 5 unified model-routing architecture...\n")

    request = AgentRequest(
        prompt="Write a Python function to inspect repository context",
        language="python",
    )
    decision = route_request(request)
    provider, model = LLMFactory.create(decision)

    print("Routing Decision:")
    print(f"  Task: {decision.task_type.value}")
    print(f"  Complexity: {decision.complexity.value}")
    print(f"  Provider: {decision.provider}")
    print(f"  Model: {model}")
    print(f"  Reason: {decision.reason}")
    print(f"  Provider ready: {provider.is_ready()}")

    memory = SessionMemory()
    memory.set_goal("Use the unified Phase 5 model-routing pipeline.")
    memory.add_turn(
        "How is model selection performed?",
        "Task classification -> complexity -> policy -> ModelRouter -> LLMFactory.",
    )

    print("\nSession Memory State:")
    print(f"  {memory.get_summary()}")
    print("\n✅ Unified routing components initialized successfully.")


if __name__ == "__main__":
    main()
