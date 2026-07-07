import logging
from functools import wraps
from typing import Any, Callable, TypeVar

import httpx
import ollama
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger("codemaster-ai")

F = TypeVar("F", bound=Callable[..., Any])


def retry_on_transient_error(*, retries: int = 3, base_delay: float = 1.0, max_delay: float = 8.0):
    """Retry async functions with exponential backoff for transient Ollama/network errors."""

    retryable_exceptions = (
        httpx.ConnectError,
        httpx.TimeoutException,
        ollama.RequestError,
        ollama.ResponseError,
    )

    def decorator(func: F) -> F:
        async def async_wrapper(*args: Any, **kwargs: Any):
            @retry(
                reraise=True,
                stop=stop_after_attempt(retries),
                wait=wait_exponential(multiplier=base_delay, max=max_delay),
                retry=retry_if_exception_type(retryable_exceptions),
                before_sleep=lambda state: logger.warning(
                    "Retrying %s after %.2f seconds (attempt %s/%s) due to %s",
                    func.__name__,
                    round(state.next_action.sleep, 2),
                    state.attempt_number,
                    retries,
                    state.outcome.exception() if state.outcome else "unknown",
                ),
            )
            async def _run():
                return await func(*args, **kwargs)

            return await _run()

        return wraps(func)(async_wrapper)  # type: ignore[return-value]

    return decorator
