"""
Retry and backoff utilities for resilient HTTP requests.
"""

import asyncio
import random
import logging
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Optional, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 5
    base_delay: float = 2.0
    max_delay: float = 300.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)


class RetryableError(Exception):
    """Exception that should trigger a retry."""
    def __init__(self, message: str, should_rotate_proxy: bool = False):
        super().__init__(message)
        self.should_rotate_proxy = should_rotate_proxy


class BlockDetectedError(Exception):
    """Exception raised when Instagram block is detected."""
    def __init__(self, block_type: str, message: str = ""):
        super().__init__(f"Block detected: {block_type}. {message}")
        self.block_type = block_type


def calculate_delay(
    attempt: int,
    config: RetryConfig,
    response_status: Optional[int] = None
) -> float:
    """
    Calculate delay before next retry attempt.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
        response_status: HTTP status code if available

    Returns:
        Delay in seconds
    """
    # Special handling for rate limiting - use longer delays
    if response_status == 429:
        base = config.base_delay * 5  # 5x longer for rate limits
    else:
        base = config.base_delay

    # Exponential backoff
    delay = base * (config.exponential_base ** attempt)

    # Cap at max delay
    delay = min(delay, config.max_delay)

    # Add jitter to prevent thundering herd
    if config.jitter:
        jitter_range = delay * 0.25
        delay = delay + random.uniform(-jitter_range, jitter_range)

    return max(delay, 0.1)  # Minimum 100ms


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic to async functions.

    Usage:
        @with_retry(RetryConfig(max_attempts=3))
        async def fetch_data():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    last_exception = e

                    if status not in config.retry_on_status:
                        raise

                    if attempt < config.max_attempts - 1:
                        delay = calculate_delay(attempt, config, status)
                        logger.warning(
                            f"HTTP {status} error, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{config.max_attempts})"
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise

                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Connection error: {e}, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{config.max_attempts})"
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise

                except RetryableError as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Retryable error: {e}, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{config.max_attempts})"
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise

            raise last_exception

        return wrapper
    return decorator
