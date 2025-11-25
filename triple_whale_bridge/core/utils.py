"""
Utility functions for Triple Whale Bridge.

Includes logging setup, retry logic, and helper functions.
"""

import logging
import os
import re
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import yaml

# Type variable for generic retry decorator
T = TypeVar("T")


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Set up logging with appropriate format and handlers.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger("triple_whale_bridge")
    logger.setLevel(log_level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file logging
    log_dir = get_log_directory()
    if log_dir:
        file_handler = logging.FileHandler(log_dir / "bridge.log")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_log_directory() -> Optional[Path]:
    """
    Get platform-appropriate log directory.

    Returns:
        Path to log directory, or None if not available
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", ""))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"

    log_dir = base / "triple-whale-bridge" / "logs"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    except OSError:
        return None


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load YAML configuration file.

    Args:
        config_path: Path to YAML file

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def get_default_config_path() -> Path:
    """Get path to default pipeline mappings config."""
    return Path(__file__).parent.parent / "config" / "pipeline_mappings.yaml"


def mask_sensitive_data(data: dict[str, Any], keys_to_mask: list[str] = None) -> dict[str, Any]:
    """
    Mask sensitive data in dictionaries for logging.

    Args:
        data: Dictionary potentially containing sensitive data
        keys_to_mask: List of keys to mask (default: common sensitive keys)

    Returns:
        Dictionary with sensitive values masked
    """
    if keys_to_mask is None:
        keys_to_mask = [
            "api_key", "apiKey", "access_token", "accessToken",
            "secret", "password", "token", "authorization"
        ]

    masked = {}
    for key, value in data.items():
        if any(sensitive.lower() in key.lower() for sensitive in keys_to_mask):
            if isinstance(value, str) and len(value) > 8:
                masked[key] = f"{value[:4]}...{value[-4:]}"
            else:
                masked[key] = "***"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_data(value, keys_to_mask)
        else:
            masked[key] = value

    return masked


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone number to E.164 format.

    Args:
        phone: Phone number in any format

    Returns:
        Phone in E.164 format (+1XXXXXXXXXX) or None
    """
    if not phone:
        return None

    # Remove all non-digit characters except leading +
    digits = re.sub(r"[^\d+]", "", phone)

    # Handle various formats
    if digits.startswith("+"):
        return digits
    elif len(digits) == 10:
        # Assume US number
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    elif len(digits) > 10:
        # Assume international with country code
        return f"+{digits}"

    return phone  # Return original if can't normalize


def normalize_email(email: Optional[str]) -> Optional[str]:
    """
    Normalize email address.

    Args:
        email: Email address

    Returns:
        Lowercase, trimmed email or None
    """
    if not email:
        return None

    return email.lower().strip()


def calculate_days_between(start: Any, end: Any = None) -> Optional[int]:
    """
    Calculate days between two dates.

    Args:
        start: Start date (datetime or ISO string)
        end: End date (defaults to now)

    Returns:
        Number of days, or None if calculation fails
    """
    from datetime import datetime

    try:
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))

        if end is None:
            end = datetime.now(start.tzinfo) if start.tzinfo else datetime.now()
        elif isinstance(end, str):
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))

        return (end - start).days
    except (ValueError, TypeError, AttributeError):
        return None


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 4,
        initial_delay: float = 2.0,
        max_delay: float = 16.0,
        exponential_base: float = 2.0,
        retry_on: tuple = (429, 500, 502, 503, 504),
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on = retry_on


def retry_with_backoff(
    config: RetryConfig = None,
    logger: logging.Logger = None,
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        config: Retry configuration
        logger: Logger instance for retry messages

    Returns:
        Decorated function
    """
    if config is None:
        config = RetryConfig()

    if logger is None:
        logger = logging.getLogger("triple_whale_bridge")

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    status_code = getattr(e, "status_code", None)
                    if status_code and status_code not in config.retry_on:
                        raise

                    if attempt < config.max_retries:
                        delay = min(
                            config.initial_delay * (config.exponential_base ** attempt),
                            config.max_delay
                        )
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)

            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    status_code = getattr(e, "status_code", None)
                    if status_code and status_code not in config.retry_on:
                        raise

                    if attempt < config.max_retries:
                        delay = min(
                            config.initial_delay * (config.exponential_base ** attempt),
                            config.max_delay
                        )
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)

            raise last_exception

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Dictionary with override values

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result
