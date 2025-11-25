"""
FastAPI Webhook Server for Triple Whale Bridge.

Receives GoHighLevel webhooks and forwards them to Triple Whale
as attribution events.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .. import __version__
from .api import TripleWhaleClient, TripleWhaleAPIError, TripleWhaleConfig
from .auth import verify_webhook_secret, verify_ghl_signature, validate_triple_whale_config
from .schema import (
    GHLWebhookPayload,
    HealthResponse,
    WebhookResponse,
)
from .transformers import GHLToTripleWhaleTransformer, PipelineConfig
from .utils import setup_logging, mask_sensitive_data

# Setup logging
logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))


# =============================================================================
# Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting Triple Whale Bridge v{__version__}")

    # Initialize components
    config_path = os.environ.get("PIPELINE_CONFIG_PATH")
    app.state.pipeline_config = PipelineConfig(config_path)
    app.state.transformer = GHLToTripleWhaleTransformer(app.state.pipeline_config)

    # Initialize Triple Whale client if configured
    try:
        tw_config = TripleWhaleConfig.from_env()
        app.state.tw_client = TripleWhaleClient(tw_config)
        logger.info("Triple Whale client initialized")
    except ValueError as e:
        logger.warning(f"Triple Whale not configured: {e}")
        app.state.tw_client = None

    yield

    # Shutdown
    if app.state.tw_client:
        await app.state.tw_client.close()
    logger.info("Triple Whale Bridge stopped")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Triple Whale Bridge",
    description="GoHighLevel to Triple Whale webhook integration service",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(TripleWhaleAPIError)
async def triple_whale_error_handler(request: Request, exc: TripleWhaleAPIError):
    """Handle Triple Whale API errors."""
    logger.error(f"Triple Whale API error: {exc.message}")
    return JSONResponse(
        status_code=502,
        content={
            "success": False,
            "message": f"Triple Whale API error: {exc.message}",
            "errors": [exc.message],
        }
    )


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service status and configuration info.
    """
    tw_status = validate_triple_whale_config()

    return HealthResponse(
        status="healthy",
        version=__version__,
        triple_whale_configured=tw_status["api_key_configured"],
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/config")
async def get_config() -> dict[str, Any]:
    """
    Get current pipeline configuration.

    Returns non-sensitive configuration information.
    """
    config = app.state.pipeline_config

    return {
        "settings": config.settings,
        "pipelines": list(config.pipelines.keys()),
        "contact_event_triggers": {
            "tags": list(config.contact_events.get("tags", {}).keys()),
            "sources": list(config.contact_events.get("sources", {}).keys()),
        },
        "value_rules": config.value_rules,
    }


@app.post("/config/reload")
async def reload_config() -> dict[str, str]:
    """Reload pipeline configuration from file."""
    app.state.pipeline_config.reload()
    app.state.transformer = GHLToTripleWhaleTransformer(app.state.pipeline_config)

    return {"status": "reloaded", "message": "Pipeline configuration reloaded"}


# =============================================================================
# Webhook Endpoints
# =============================================================================

@app.post("/webhook/ghl", response_model=WebhookResponse)
async def handle_ghl_webhook(
    request: Request,
    _auth: bool = Depends(verify_webhook_secret),
) -> WebhookResponse:
    """
    Main webhook endpoint for GoHighLevel events.

    Accepts any GHL webhook payload (pipeline changes, contact events, etc.)
    and transforms it to a Triple Whale attribution event.

    Headers:
        - X-Webhook-Secret: Optional webhook secret for authentication
        - X-GHL-Signature: Optional GHL signature verification
        - Content-Type: application/json

    Returns:
        WebhookResponse with success status and event details
    """
    # Parse request body
    try:
        body = await request.body()
        payload_dict = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Verify GHL signature if configured
    ghl_signature = request.headers.get("X-GHL-Signature")
    if not verify_ghl_signature(body, ghl_signature):
        raise HTTPException(status_code=401, detail="Invalid GHL signature")

    # Log incoming webhook (masked)
    logger.info(f"Received GHL webhook: {mask_sensitive_data(payload_dict)}")

    # Parse payload
    try:
        ghl_payload = GHLWebhookPayload(**payload_dict)
    except Exception as e:
        logger.error(f"Failed to parse GHL payload: {e}")
        return WebhookResponse(
            success=False,
            message=f"Failed to parse payload: {str(e)}",
            errors=[str(e)],
        )

    # Transform to Triple Whale event
    transformer: GHLToTripleWhaleTransformer = app.state.transformer
    tw_event = transformer.transform(ghl_payload)

    if not tw_event:
        return WebhookResponse(
            success=False,
            message="Could not transform to Triple Whale event (missing email/phone or unmapped stage)",
            errors=["No customer identifier or stage mapping"],
        )

    # Send to Triple Whale
    tw_client: Optional[TripleWhaleClient] = app.state.tw_client

    if not tw_client:
        logger.warning("Triple Whale client not configured, event not sent")
        return WebhookResponse(
            success=False,
            message="Triple Whale not configured",
            event_type=tw_event.type.value,
            errors=["TRIPLE_WHALE_API_KEY not set"],
        )

    try:
        result = await tw_client.send_event(tw_event)
        logger.info(f"Event sent to Triple Whale: {tw_event.type.value}")

        return WebhookResponse(
            success=True,
            message="Event sent to Triple Whale",
            event_type=tw_event.type.value,
            triple_whale_status=200,
        )

    except TripleWhaleAPIError as e:
        logger.error(f"Failed to send event: {e}")
        return WebhookResponse(
            success=False,
            message=f"Triple Whale API error: {e.message}",
            event_type=tw_event.type.value,
            triple_whale_status=e.status_code,
            errors=[e.message],
        )


@app.post("/webhook/ghl/opportunity", response_model=WebhookResponse)
async def handle_opportunity_webhook(
    request: Request,
    _auth: bool = Depends(verify_webhook_secret),
) -> WebhookResponse:
    """
    Dedicated endpoint for GHL opportunity/pipeline stage webhooks.

    Use this endpoint when configuring GHL workflow with
    "Pipeline Stage Changed" trigger for best results.
    """
    # Same logic as main webhook
    return await handle_ghl_webhook(request, _auth)


@app.post("/webhook/ghl/contact", response_model=WebhookResponse)
async def handle_contact_webhook(
    request: Request,
    tag: Optional[str] = None,
    _auth: bool = Depends(verify_webhook_secret),
) -> WebhookResponse:
    """
    Dedicated endpoint for GHL contact events (tag added, etc.).

    Query params:
        - tag: Tag that triggered this webhook (for tag-based mappings)

    Use for workflows triggered by tag additions or contact updates.
    """
    # Parse request
    try:
        payload_dict = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Parse payload
    try:
        ghl_payload = GHLWebhookPayload(**payload_dict)
    except Exception as e:
        return WebhookResponse(
            success=False,
            message=f"Failed to parse payload: {str(e)}",
            errors=[str(e)],
        )

    # Use contact event transformer
    transformer: GHLToTripleWhaleTransformer = app.state.transformer
    tw_event = transformer.transform_contact_event(ghl_payload, trigger_tag=tag)

    if not tw_event:
        return WebhookResponse(
            success=False,
            message="Could not transform contact event",
            errors=["No customer identifier"],
        )

    # Send to Triple Whale
    tw_client: Optional[TripleWhaleClient] = app.state.tw_client

    if not tw_client:
        return WebhookResponse(
            success=False,
            message="Triple Whale not configured",
            event_type=tw_event.type.value,
            errors=["TRIPLE_WHALE_API_KEY not set"],
        )

    try:
        await tw_client.send_event(tw_event)
        return WebhookResponse(
            success=True,
            message="Contact event sent to Triple Whale",
            event_type=tw_event.type.value,
            triple_whale_status=200,
        )
    except TripleWhaleAPIError as e:
        return WebhookResponse(
            success=False,
            message=f"Triple Whale API error: {e.message}",
            event_type=tw_event.type.value,
            triple_whale_status=e.status_code,
            errors=[e.message],
        )


# =============================================================================
# Test Endpoints
# =============================================================================

@app.post("/test/transform")
async def test_transform(request: Request) -> dict[str, Any]:
    """
    Test endpoint to preview transformation without sending to Triple Whale.

    Useful for debugging and verifying mappings.
    """
    try:
        payload_dict = await request.json()
        ghl_payload = GHLWebhookPayload(**payload_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    transformer: GHLToTripleWhaleTransformer = app.state.transformer
    tw_event = transformer.transform(ghl_payload)

    if not tw_event:
        return {
            "success": False,
            "message": "Could not transform payload",
            "ghl_payload": payload_dict,
            "triple_whale_event": None,
        }

    return {
        "success": True,
        "message": "Transformation successful (not sent)",
        "ghl_payload": {
            "pipeline_name": ghl_payload.pipeline_name,
            "pipeline_stage": ghl_payload.pipeline_stage,
            "email": ghl_payload.email,
            "contact_id": ghl_payload.contact_id,
        },
        "triple_whale_event": tw_event.model_dump_for_api(),
    }


@app.post("/test/send")
async def test_send_event(request: Request) -> dict[str, Any]:
    """
    Test endpoint to send a raw event directly to Triple Whale.

    Bypasses GHL transformation - send Triple Whale event format directly.
    """
    tw_client: Optional[TripleWhaleClient] = app.state.tw_client

    if not tw_client:
        raise HTTPException(
            status_code=503,
            detail="Triple Whale not configured"
        )

    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # Send directly to Triple Whale
    try:
        from .schema import TripleWhaleEvent, TripleWhaleEventType

        event = TripleWhaleEvent(
            type=TripleWhaleEventType(payload.get("type", "custom")),
            email=payload.get("email"),
            phone=payload.get("phone"),
            properties=payload.get("properties", {}),
        )

        result = await tw_client.send_event(event)

        return {
            "success": True,
            "message": "Test event sent to Triple Whale",
            "event": event.model_dump_for_api(),
            "response": result,
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "event": payload,
        }
