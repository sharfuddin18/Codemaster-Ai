"""Authoritative task classification and model-routing policy.

Phase 5 consolidates production model selection into this module. Entry
points create an AgentRequest, ModelRouter produces one structured decision,
and LLMFactory is the only provider-instantiation boundary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class TaskType(str, Enum):
    """Repository-supported high-level coding task categories."""

    GENERATION = "generation"
    FIX = "fix"
    COMPLETION = "completion"
    REFACTOR = "refactor"
    ARCHITECTURE = "architecture"
    AUDIT = "audit"


class TaskComplexity(str, Enum):
    """Complexity used by the deterministic model policy."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class AgentRequest:
    """Structured request entering the routing system."""

    prompt: str
    task_type: TaskType | None = None
    language: str | None = None
    model_override: str | None = None
    provider_override: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.prompt or not self.prompt.strip():
            raise ValueError("AgentRequest.prompt must not be empty")


@dataclass(frozen=True)
class RoutingDecision:
    """Complete deterministic provider/model decision."""

    task_type: TaskType
    complexity: TaskComplexity
    provider: str
    model: str
    reason: str


@dataclass(frozen=True)
class AgentResult:
    """Structured result leaving the agent/model-routing system."""

    response: str
    decision: RoutingDecision


class TaskClassifier:
    """Single authoritative classifier for task type and complexity."""

    _HIGH_COMPLEXITY = {"refactor", "architecture", "audit"}
    _MEDIUM_COMPLEXITY = {"fix", "debug", "optimize", "review"}

    def classify(self, request: AgentRequest) -> tuple[TaskType, TaskComplexity]:
        task_type = request.task_type or self._classify_type(request.prompt)
        complexity = self._classify_complexity(request.prompt, task_type)
        return task_type, complexity

    def _classify_type(self, prompt: str) -> TaskType:
        text = prompt.lower()
        if re.search(r"\b(audit)\b", text):
            return TaskType.AUDIT
        if re.search(r"\b(refactor|architecture)\b", text):
            return TaskType.REFACTOR if "refactor" in text else TaskType.ARCHITECTURE
        if re.search(r"\b(fix|debug|bug|repair)\b", text):
            return TaskType.FIX
        return TaskType.GENERATION

    def _classify_complexity(self, prompt: str, task_type: TaskType) -> TaskComplexity:
        if task_type.value in self._HIGH_COMPLEXITY:
            return TaskComplexity.HIGH
        if task_type.value in self._MEDIUM_COMPLEXITY:
            return TaskComplexity.MEDIUM
        return TaskComplexity.LOW


class ModelPolicy:
    """Explicit, deterministic model policy.

    Model names are the models already used by the repository's existing
    routing behavior; Phase 5 centralizes that behavior rather than inventing
    new providers or capabilities.
    """

    DEFAULT_MODEL = "qwen2.5-coder:1.5b"

    _RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("mistral:7b-instruct", "Data Science/ML detected", (
            "machine learning", "ml", "pandas", "numpy", "dataframe",
            "scikit", "keras", "data science", "deep learning", "regression",
            "classification", "training", "inference", "stats",
        )),
        ("codellama:7b-instruct", "Python detected", ("python",)),
        ("qwen2.5-coder:1.5b", "JavaScript/Web detected", (
            "javascript", "js", "web", "html", "css", "browser",
            "frontend", "react", "vue",
        )),
        ("mistral:7b-instruct", "Java detected", ("java",)),
        ("mistral:7b-instruct", "C/C++ detected", ("c++", "cpp", "c language")),
        ("mistral:7b-instruct", "C# detected", ("c#",)),
        ("mistral:7b-instruct", "Go detected", ("golang", "go lang")),
        ("mistral:7b-instruct", "Rust detected", ("rust",)),
        ("mistral:7b-instruct", "Ruby detected", ("ruby",)),
        ("mistral:7b-instruct", "TypeScript detected", ("typescript",)),
        ("mistral:7b-instruct", "Swift/Kotlin detected", ("swift", "kotlin", "android", "ios")),
        ("qwen2.5-coder:1.5b", "SQL/Database detected", (
            "sql", "query", "database", "mysql", "postgres", "sqlite",
            "mongodb", "oracle", "db", "table", "column",
        )),
        ("qwen2.5-coder:1.5b", "Shell/Bash detected", (
            "bash", "shell", "sh", "shell script", "bash script",
            "automation", "cli", "powershell",
        )),
        ("qwen2.5-coder:1.5b", "PHP detected", ("php",)),
        ("qwen2.5-coder:1.5b", "DevOps detected", (
            "yaml", "docker", "docker-compose", "compose", "kubernetes",
        )),
        ("qwen2.5-coder:1.5b", "Frontend/UI/UX detected", (
            "html", "css", "ui", "ux", "responsive", "design",
        )),
        ("mistral:7b-instruct", "Statistical/Matlab/R/SAS detected", (
            "matlab", "r language", "sas", "regression analysis", "statistical",
        )),
    )

    @staticmethod
    def _matches(keyword: str, text: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text))

    def choose(
        self,
        request: AgentRequest,
        task_type: TaskType,
        complexity: TaskComplexity,
    ) -> tuple[str, str]:
        if request.model_override:
            return request.model_override.strip(), "Explicit model override"

        text = f"{request.prompt} {request.language or ''}".lower()
        for model, reason, keywords in self._RULES:
            if any(self._matches(keyword, text) for keyword in keywords):
                return model, reason

        if complexity is TaskComplexity.HIGH:
            return self.DEFAULT_MODEL, "High-complexity task using configured default model"
        return self.DEFAULT_MODEL, "Default fallback"


class ModelRouter:
    """The single authoritative production model router."""

    SUPPORTED_PROVIDERS = frozenset({"ollama", "openai", "fallback"})

    def __init__(self, classifier: TaskClassifier | None = None, policy: ModelPolicy | None = None):
        self.classifier = classifier or TaskClassifier()
        self.policy = policy or ModelPolicy()

    def route(self, request: AgentRequest) -> RoutingDecision:
        task_type, complexity = self.classifier.classify(request)
        provider = (request.provider_override or "ollama").strip().lower()
        if provider not in self.SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        model, reason = self.policy.choose(request, task_type, complexity)
        if not model:
            raise ValueError("ModelPolicy produced an empty model")
        return RoutingDecision(
            task_type=task_type,
            complexity=complexity,
            provider=provider,
            model=model,
            reason=reason,
        )


DEFAULT_MODEL_ROUTER = ModelRouter()


def classify_request(
    prompt: str,
    language: str | None = None,
    task_type: TaskType | None = None,
) -> tuple[TaskType, TaskComplexity]:
    """Convenience entry point delegating to the authoritative classifier."""

    return DEFAULT_MODEL_ROUTER.classifier.classify(
        AgentRequest(prompt=prompt, language=language, task_type=task_type)
    )


def route_request(request: AgentRequest) -> RoutingDecision:
    """Convenience entry point delegating to the authoritative router."""

    return DEFAULT_MODEL_ROUTER.route(request)


def select_best_model(prompt: str, language: str | None = None) -> dict[str, str]:
    """Backward-compatible facade backed by ModelRouter."""

    decision = route_request(AgentRequest(prompt=prompt, language=language))
    return {"model": decision.model, "reason": decision.reason}
