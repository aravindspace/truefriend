"""Retries — §5: exponential backoff on 429/5xx; one structured-output
re-ask on validation failure, then a safe default.

Gateway-level 429/5xx retries already live in the LiteLLM Router (P1.2);
``backoff`` covers non-gateway calls (stores, embeddings). ``ask_structured``
is the single re-ask discipline every structured LLM output goes through.
"""

import logging
import time
from typing import Callable, Optional, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("arjun.harness")

M = TypeVar("M", bound=BaseModel)


def backoff(
    fn: Callable,
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
):
    """Call ``fn()``; on a retryable error wait base_delay * 2^n and retry."""
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            if attempt == attempts - 1:
                raise
            delay = base_delay * (2**attempt)
            logger.warning("retry %d/%d after %s: %s", attempt + 1, attempts, delay, exc)
            time.sleep(delay)


def ask_structured(
    call: Callable[[Optional[str]], str],
    schema: type[M],
    *,
    default: M,
) -> M:
    """Validate ``call``'s output against ``schema`` with ONE re-ask.

    ``call(feedback)`` returns raw model text; ``feedback`` is None on the
    first ask and the validation error text on the single re-ask. If both
    fail, the safe ``default`` is returned — never an exception upward.
    """
    feedback = None
    for _ in range(2):
        try:
            return schema.model_validate_json(call(feedback))
        except (ValidationError, ValueError) as exc:
            feedback = f"Your previous output was invalid: {exc}. Reply with valid JSON only."
    logger.warning("structured output failed twice for %s — safe default used", schema.__name__)
    return default
