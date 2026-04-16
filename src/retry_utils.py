# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Retry utilities for AI client implementations.

This module provides retry decorators and utilities for handling transient
failures like rate limits, service unavailability, and network errors.
"""

from __future__ import annotations

import logging
from typing import Any

from tenacity import (
    Retrying,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Base exception for rate limit errors."""

    pass


class ServiceUnavailableError(Exception):
    """Exception for service unavailable errors (503)."""

    pass


RETRYABLE_EXCEPTIONS = (
    RateLimitError,
    ServiceUnavailableError,
    ConnectionError,
    TimeoutError,
)


def get_retry_decorator(
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 60,
    exponential_base: float = 2,
    jitter: bool = True,
    retry_exceptions: tuple = RETRYABLE_EXCEPTIONS,
    log_level: int = logging.INFO,
):
    """Create a retry decorator with configurable parameters.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add jitter to wait times
        retry_exceptions: Tuple of exception types to retry on
        log_level: Logging level for retry messages

    Returns:
        Configured retry decorator

    Example:
        >>> @get_retry_decorator(max_attempts=5, min_wait=2)
        ... def my_api_call():
        ...     return client.generate_response("Hello")

    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(
            initial=min_wait, max=max_wait, exp_base=exponential_base, jitter=jitter
        ),
        retry=retry_if_exception_type(retry_exceptions),
        before_sleep=before_sleep_log(logger, log_level),
        reraise=True,
    )


def get_configured_retry_decorator():
    """Get retry decorator configured from global config, with fallback to defaults.

    Reads retry settings from the application config (``config/main.yaml``).
    Falls back to ``get_retry_decorator()`` defaults when config is unavailable.

    Returns:
        Configured retry decorator

    """
    from .config import get_config

    try:
        app_config = get_config()
        retry_settings = getattr(app_config, "retry", None)

        if retry_settings:
            return get_retry_decorator(
                max_attempts=getattr(retry_settings, "max_attempts", 3),
                min_wait=getattr(retry_settings, "min_wait_seconds", 1),
                max_wait=getattr(retry_settings, "max_wait_seconds", 60),
                exponential_base=getattr(retry_settings, "exponential_base", 2),
                jitter=getattr(retry_settings, "exponential_jitter", True),
            )
    except Exception as e:
        logger.debug(f"Could not load retry config: {e}")

    return get_retry_decorator()


def should_retry_exception(exception: Exception) -> bool:
    """Determine if an exception should trigger a retry.

    Args:
        exception: The exception to check

    Returns:
        True if the exception should trigger a retry

    """
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True

    exception_str = str(exception).lower()
    retry_indicators = [
        "429",
        "rate limit",
        "too many requests",
        "quota exceeded",
        "resource_exhausted",
        "503",
        "service unavailable",
        "502",
        "bad gateway",
        "504",
        "gateway timeout",
        "timeout",
        "connection",
    ]

    return any(indicator in exception_str for indicator in retry_indicators)


def extract_retry_after(exception: Exception) -> float | None:
    """Extract retry-after delay from exception if available.

    Args:
        exception: The exception to extract retry-after from

    Returns:
        Retry delay in seconds, or None if not available

    """
    exception_str = str(exception)

    import re

    patterns = [
        r"retry in (\d+(?:\.\d+)?)\s*s",
        r"retry after (\d+(?:\.\d+)?)\s*s",
        r"retrydelay[\":\s]+(\d+)",
        r"wait (\d+(?:\.\d+)?)\s*seconds",
    ]

    for pattern in patterns:
        match = re.search(pattern, exception_str, re.IGNORECASE)
        if match:
            return float(match.group(1))

    return None


def retry_with_backoff(
    func: Any,
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 60,
    exponential_base: float = 2,
    jitter: bool = True,
    *args,
    **kwargs,
) -> Any:
    """Execute a function with retry and exponential backoff.

    Args:
        func: Function to execute
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add jitter to wait times
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of func if successful

    Raises:
        RetryError: If all retry attempts fail
        Exception: Original exception if not retryable

    Example:
        >>> result = retry_with_backoff(
        ...     client.generate_response,
        ...     max_attempts=5,
        ...     prompt="Hello"
        ... )

    """
    retryer = Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(
            initial=min_wait, max=max_wait, exp_base=exponential_base, jitter=jitter
        ),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True,
    )

    return retryer(func, *args, **kwargs)


def create_rate_limit_error(exception: Exception) -> RateLimitError:
    """Create a RateLimitError from another exception.

    Args:
        exception: Original exception

    Returns:
        RateLimitError with information from original exception

    """
    retry_after = extract_retry_after(exception)
    if retry_after:
        return RateLimitError(
            f"Rate limit exceeded. Retry after {retry_after}s. Original error: {exception}"
        )
    return RateLimitError(f"Rate limit exceeded. Original error: {exception}")
