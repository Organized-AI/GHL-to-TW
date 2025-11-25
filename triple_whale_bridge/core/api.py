"""
Triple Whale API Client.

Handles all communication with the Triple Whale Data-In API,
including authentication, request formatting, and error handling.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import httpx

from .schema import TripleWhaleEvent
from .utils import mask_sensitive_data, RetryConfig

logger = logging.getLogger("triple_whale_bridge")


# =============================================================================
# Exceptions
# =============================================================================

class TripleWhaleAPIError(Exception):
    """Base exception for Triple Whale API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(self.message)


class TripleWhaleAuthError(TripleWhaleAPIError):
    """Authentication error with Triple Whale API."""
    pass


class TripleWhaleRateLimitError(TripleWhaleAPIError):
    """Rate limit exceeded."""
    pass


class TripleWhaleValidationError(TripleWhaleAPIError):
    """Validation error in request payload."""
    pass


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class TripleWhaleConfig:
    """Configuration for Triple Whale API client."""

    api_key: str
    base_url: str = "https://api.triplewhale.com/api/v2"

    # Rate limits (per minute)
    data_in_rate_limit: int = 25000
    event_rate_limit: int = 1000
    event_max_payload_kb: int = 3

    # Retry configuration
    max_retries: int = 4
    initial_retry_delay: float = 2.0
    max_retry_delay: float = 16.0

    # Timeout (seconds)
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "TripleWhaleConfig":
        """Create configuration from environment variables."""
        api_key = os.environ.get("TRIPLE_WHALE_API_KEY")

        if not api_key:
            raise ValueError(
                "TRIPLE_WHALE_API_KEY environment variable is required. "
                "Create an API key at Settings > API Keys in your Triple Whale dashboard."
            )

        return cls(
            api_key=api_key,
            base_url=os.environ.get(
                "TRIPLE_WHALE_BASE_URL",
                "https://api.triplewhale.com/api/v2"
            ),
            timeout=float(os.environ.get("TRIPLE_WHALE_TIMEOUT", "30")),
        )


# =============================================================================
# API Client
# =============================================================================

class TripleWhaleClient:
    """
    Async client for Triple Whale Data-In API.

    Handles:
    - Event submission with retry logic
    - Rate limiting
    - Error handling and logging
    """

    def __init__(self, config: Optional[TripleWhaleConfig] = None):
        """
        Initialize Triple Whale client.

        Args:
            config: API configuration. If None, loads from environment.
        """
        self.config = config or TripleWhaleConfig.from_env()
        self._client: Optional[httpx.AsyncClient] = None
        self._retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            initial_delay=self.config.initial_retry_delay,
            max_delay=self.config.max_retry_delay,
            retry_on=(429, 500, 502, 503, 504),
        )

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "x-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "TripleWhaleBridge/0.1.0",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # -------------------------------------------------------------------------
    # API Methods
    # -------------------------------------------------------------------------

    async def send_event(self, event: TripleWhaleEvent) -> dict[str, Any]:
        """
        Send an offline attribution event to Triple Whale.

        Endpoint: POST /data-in/event
        Rate limit: 1,000 events/min
        Max payload: 3 KB

        Args:
            event: Triple Whale event to send

        Returns:
            API response as dictionary

        Raises:
            TripleWhaleAPIError: On API errors
            TripleWhaleAuthError: On authentication errors
            TripleWhaleRateLimitError: On rate limit exceeded
            TripleWhaleValidationError: On validation errors
        """
        # Validate event has required identifiers
        if not event.email and not event.phone:
            raise TripleWhaleValidationError(
                "Event must have either email or phone for attribution"
            )

        payload = event.model_dump_for_api()

        # Log request (masked)
        logger.info(
            f"Sending {event.type.value} event for "
            f"{event.email or event.phone}"
        )
        logger.debug(f"Event payload: {mask_sensitive_data(payload)}")

        return await self._make_request(
            method="POST",
            endpoint="/data-in/event",
            json=payload
        )

    async def validate_api_key(self) -> dict[str, Any]:
        """
        Validate the API key by calling the /me endpoint.

        Returns:
            API key information

        Raises:
            TripleWhaleAuthError: If API key is invalid
        """
        return await self._make_request(
            method="GET",
            endpoint="/users/api-keys/me"
        )

    async def send_order(self, order_data: dict[str, Any]) -> dict[str, Any]:
        """
        Send order data to Triple Whale (for custom sales platforms).

        Endpoint: POST /data-in/orders

        Args:
            order_data: Order data dictionary

        Returns:
            API response
        """
        logger.info(f"Sending order: {order_data.get('order_id', 'unknown')}")

        return await self._make_request(
            method="POST",
            endpoint="/data-in/orders",
            json=order_data
        )

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method
            endpoint: API endpoint path
            json: JSON body
            params: Query parameters

        Returns:
            Response data

        Raises:
            TripleWhaleAPIError: On API errors
        """
        last_exception = None
        delays = [
            self._retry_config.initial_delay * (self._retry_config.exponential_base ** i)
            for i in range(self._retry_config.max_retries)
        ]

        for attempt in range(self._retry_config.max_retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=endpoint,
                    json=json,
                    params=params,
                )

                # Handle response
                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception:
                        return {"status": "success", "raw": response.text}

                # Handle errors
                error_body = response.text
                status_code = response.status_code

                if status_code == 401:
                    raise TripleWhaleAuthError(
                        "Invalid API key. Check your TRIPLE_WHALE_API_KEY.",
                        status_code=status_code,
                        response_body=error_body
                    )

                if status_code == 403:
                    raise TripleWhaleAuthError(
                        "API key lacks required scope. "
                        "Ensure 'Orders: Write' scope is enabled.",
                        status_code=status_code,
                        response_body=error_body
                    )

                if status_code == 422:
                    raise TripleWhaleValidationError(
                        f"Validation error: {error_body}",
                        status_code=status_code,
                        response_body=error_body
                    )

                if status_code == 429:
                    raise TripleWhaleRateLimitError(
                        "Rate limit exceeded. Max 1,000 events/min.",
                        status_code=status_code,
                        response_body=error_body
                    )

                # Retryable errors (5xx)
                if status_code >= 500:
                    raise TripleWhaleAPIError(
                        f"Server error: {error_body}",
                        status_code=status_code,
                        response_body=error_body
                    )

                # Other client errors - don't retry
                raise TripleWhaleAPIError(
                    f"Request failed: {error_body}",
                    status_code=status_code,
                    response_body=error_body
                )

            except (TripleWhaleAuthError, TripleWhaleValidationError):
                # Don't retry auth or validation errors
                raise

            except (TripleWhaleRateLimitError, TripleWhaleAPIError) as e:
                last_exception = e

                # Check if we should retry
                if attempt < self._retry_config.max_retries:
                    delay = min(delays[attempt], self._retry_config.max_delay)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

            except httpx.TimeoutException as e:
                last_exception = TripleWhaleAPIError(
                    f"Request timed out after {self.config.timeout}s",
                    status_code=None
                )

                if attempt < self._retry_config.max_retries:
                    delay = min(delays[attempt], self._retry_config.max_delay)
                    logger.warning(
                        f"Timeout (attempt {attempt + 1}). Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise last_exception

            except httpx.RequestError as e:
                last_exception = TripleWhaleAPIError(
                    f"Network error: {str(e)}",
                    status_code=None
                )

                if attempt < self._retry_config.max_retries:
                    delay = min(delays[attempt], self._retry_config.max_delay)
                    logger.warning(
                        f"Network error (attempt {attempt + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise last_exception

        raise last_exception


# =============================================================================
# Convenience Functions
# =============================================================================

async def send_event_to_triple_whale(
    event: TripleWhaleEvent,
    api_key: Optional[str] = None
) -> dict[str, Any]:
    """
    Convenience function to send a single event.

    Args:
        event: Event to send
        api_key: API key (uses environment if not provided)

    Returns:
        API response
    """
    config = None
    if api_key:
        config = TripleWhaleConfig(api_key=api_key)

    async with TripleWhaleClient(config) as client:
        return await client.send_event(event)


def create_client_from_env() -> TripleWhaleClient:
    """
    Create a Triple Whale client from environment variables.

    Returns:
        Configured TripleWhaleClient
    """
    return TripleWhaleClient(TripleWhaleConfig.from_env())
