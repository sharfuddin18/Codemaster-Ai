import pytest

from backend.app.llm.factory import LLMFactory
from backend.app.llm.providers.fallback import FallbackProvider
from backend.app.llm.providers.ollama import OllamaProvider
from backend.app.llm.routing import (
    AgentRequest,
    AgentResult,
    ModelRouter,
    RoutingDecision,
    TaskClassifier,
    TaskComplexity,
    TaskType,
    classify_request,
    route_request,
    select_best_model,
)


def test_task_classifier_generation_and_fix_complexity():
    classifier = TaskClassifier()
    task_type, complexity = classifier.classify(
        AgentRequest("Write a Python function to add two numbers")
    )
    assert task_type is TaskType.GENERATION
    assert complexity is TaskComplexity.LOW

    task_type, complexity = classifier.classify(
        AgentRequest("Fix the broken parser and debug the failing test")
    )
    assert task_type is TaskType.FIX
    assert complexity is TaskComplexity.MEDIUM


@pytest.mark.parametrize(
    ("prompt", "language", "expected_model"),
    [
        ("Write a python script to parse JSON", "python", "codellama:7b-instruct"),
        ("Train a random forest regression model using pandas", "python", "mistral:7b-instruct"),
        ("Create a responsive React component", "javascript", "qwen2.5-coder:1.5b"),
        ("Hello world", None, "qwen2.5-coder:1.5b"),
    ],
)
def test_model_policy_preserves_existing_routing(prompt, language, expected_model):
    decision = route_request(AgentRequest(prompt=prompt, language=language))
    assert decision.provider == "ollama"
    assert decision.model == expected_model


def test_model_policy_is_deterministic():
    request = AgentRequest("Create a Python parser", language="python")
    router = ModelRouter()
    assert router.route(request) == router.route(request)


def test_routing_decision_is_structured_and_complete():
    decision = route_request(AgentRequest("Fix this Python bug", language="python"))
    assert isinstance(decision, RoutingDecision)
    assert decision.task_type is TaskType.FIX
    assert decision.complexity is TaskComplexity.MEDIUM
    assert decision.provider == "ollama"
    assert decision.model == "codellama:7b-instruct"
    assert decision.reason


def test_invalid_provider_is_rejected():
    with pytest.raises(ValueError, match="Unsupported provider"):
        ModelRouter().route(
            AgentRequest("generate code", provider_override="not-a-provider")
        )


def test_invalid_request_is_rejected():
    with pytest.raises(ValueError, match="prompt"):
        AgentRequest("")


def test_factory_uses_structured_decision():
    decision = route_request(AgentRequest("Write Python code", language="python"))
    provider, model = LLMFactory.create(decision)
    assert isinstance(provider, OllamaProvider)
    assert model == "codellama:7b-instruct"


def test_factory_fallback_provider_remains_available():
    provider = LLMFactory.create_provider("fallback")
    assert isinstance(provider, FallbackProvider)
    assert provider.is_ready() is False


def test_legacy_model_selection_facade_delegates_to_router():
    result = select_best_model("Write a python function", "python")
    assert result == {
        "model": "codellama:7b-instruct",
        "reason": "Python detected",
    }


def test_classifier_convenience_entry_point():
    task_type, complexity = classify_request("audit the architecture")
    assert task_type is TaskType.AUDIT
    assert complexity is TaskComplexity.HIGH


def test_agent_result_is_structured():
    decision = route_request(AgentRequest("Hello"))
    result = AgentResult(response="mock response", decision=decision)
    assert result.response == "mock response"
    assert result.decision is decision
