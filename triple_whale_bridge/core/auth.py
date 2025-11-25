"""
Authentication and security for Triple Whale Bridge.

Handles webhook signature verification and API authentication.
"""

import hashlib
import hmac
import logging
import os
from typing import Optional

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger("triple_whale_bridge")


# =============================================================================
# API Key Authentication
# =============================================================================

api_key_header = APIKeyHeader(name="X-Webhook-Secret", auto_error=False)


def get_webhook_secret() -> Optional[str]:
    """Get webhook secret from environment."""
    return os.environ.get("WEBHOOK_SECRET")


async def verify_webhook_secret(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
) -> bool:
    """
    Verify webhook request has valid secret.

    This is optional - if WEBHOOK_SECRET is not set, all requests are allowed.
    When set, requests must include X-Webhook-Secret header.

    Args:
        request: FastAPI request
        api_key: API key from header

    Returns:
        True if valid or no secret configured

    Raises:
        HTTPException: If secret is configured but request doesn't match
    """
    expected_secret = get_webhook_secret()

    if not expected_secret:
        # No secret configured, allow all requests
        logger.debug("No webhook secret configured, skipping verification")
        return True

    if not api_key:
        logger.warning("Webhook secret configured but no X-Webhook-Secret header provided")
        raise HTTPException(
            status_code=401,
            detail="Missing X-Webhook-Secret header"
        )

    if not hmac.compare_digest(api_key, expected_secret):
        logger.warning("Invalid webhook secret provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook secret"
        )

    return True


# =============================================================================
# GoHighLevel Signature Verification
# =============================================================================

def verify_ghl_signature(
    payload: bytes,
    signature: Optional[str],
    secret: Optional[str] = None,
) -> bool:
    """
    Verify GoHighLevel webhook signature.

    GHL uses HMAC-SHA256 for webhook signatures.

    Args:
        payload: Raw request body
        signature: Signature from X-GHL-Signature header
        secret: Webhook secret (uses env var if not provided)

    Returns:
        True if signature is valid or no secret configured
    """
    if secret is None:
        secret = os.environ.get("GHL_WEBHOOK_SECRET")

    if not secret:
        # No GHL secret configured
        return True

    if not signature:
        logger.warning("GHL webhook secret configured but no signature in request")
        return False

    # Calculate expected signature
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Compare signatures
    if hmac.compare_digest(signature, expected_signature):
        return True

    # Try with 'sha256=' prefix
    if signature.startswith("sha256="):
        return hmac.compare_digest(signature[7:], expected_signature)

    logger.warning("GHL webhook signature verification failed")
    return False


# =============================================================================
# Triple Whale API Key Validation
# =============================================================================

def validate_triple_whale_config() -> dict[str, bool]:
    """
    Validate Triple Whale configuration.

    Returns:
        Dictionary with configuration status
    """
    api_key = os.environ.get("TRIPLE_WHALE_API_KEY")

    return {
        "api_key_configured": bool(api_key),
        "api_key_length": len(api_key) if api_key else 0,
    }


def get_triple_whale_api_key() -> str:
    """
    Get Triple Whale API key from environment.

    Returns:
        API key string

    Raises:
        ValueError: If API key not configured
    """
    api_key = os.environ.get("TRIPLE_WHALE_API_KEY")

    if not api_key:
        raise ValueError(
            "TRIPLE_WHALE_API_KEY environment variable is required. "
            "Create an API key at Settings > API Keys in Triple Whale."
        )

    return api_key
