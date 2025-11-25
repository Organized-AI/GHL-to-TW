"""
GHL to Triple Whale Transformers.

Transforms GoHighLevel webhook payloads into Triple Whale attribution events
based on configurable pipeline stage mappings.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .schema import (
    GHLWebhookPayload,
    TripleWhaleEvent,
    TripleWhaleEventProperties,
    TripleWhaleEventType,
)
from .utils import (
    calculate_days_between,
    get_default_config_path,
    load_yaml_config,
    normalize_email,
    normalize_phone,
)

logger = logging.getLogger("triple_whale_bridge")


class PipelineConfig:
    """
    Pipeline configuration loaded from YAML.

    Provides access to stage mappings, field mappings, and value rules.
    """

    def __init__(self, config_path: Optional[str | Path] = None):
        """
        Load pipeline configuration.

        Args:
            config_path: Path to YAML config file. Uses default if not provided.
        """
        self.config_path = Path(config_path) if config_path else get_default_config_path()
        self._config: dict = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            self._config = load_yaml_config(self.config_path)
            logger.info(f"Loaded pipeline config from {self.config_path}")
        except FileNotFoundError:
            logger.warning(
                f"Config file not found at {self.config_path}. "
                "Using default mappings."
            )
            self._config = self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}. Using defaults.")
            self._config = self._get_default_config()

    def _get_default_config(self) -> dict:
        """Return minimal default configuration."""
        return {
            "settings": {
                "default_currency": "USD",
                "send_unmapped_stages": True,
                "default_event_type": "custom",
            },
            "pipelines": {
                "default": {
                    "stages": {
                        "New Lead": {"event_type": "lead"},
                        "Qualified": {"event_type": "mql"},
                        "Demo Scheduled": {"event_type": "book_demo"},
                        "Proposal": {"event_type": "opportunity"},
                        "Closed Won": {"event_type": "custom", "custom_event_name": "closed_won"},
                    }
                }
            },
            "value_rules": {
                "calculation_method": "actual",
            }
        }

    @property
    def settings(self) -> dict:
        """Get global settings."""
        return self._config.get("settings", {})

    @property
    def pipelines(self) -> dict:
        """Get pipeline definitions."""
        return self._config.get("pipelines", {})

    @property
    def contact_events(self) -> dict:
        """Get contact event mappings."""
        return self._config.get("contact_events", {})

    @property
    def field_mappings(self) -> dict:
        """Get field mapping definitions."""
        return self._config.get("field_mappings", {})

    @property
    def value_rules(self) -> dict:
        """Get value calculation rules."""
        return self._config.get("value_rules", {})

    def get_stage_mapping(
        self,
        pipeline_name: str,
        stage_name: str
    ) -> Optional[dict]:
        """
        Get mapping for a specific pipeline stage.

        Args:
            pipeline_name: Name of the pipeline
            stage_name: Name of the stage

        Returns:
            Stage mapping dict or None if not found
        """
        # Try exact pipeline match
        pipeline = self.pipelines.get(pipeline_name)
        if pipeline:
            stages = pipeline.get("stages", {})
            if stage_name in stages:
                return stages[stage_name]

        # Try case-insensitive match
        for p_name, p_config in self.pipelines.items():
            if p_name.lower() == pipeline_name.lower():
                stages = p_config.get("stages", {})
                for s_name, s_config in stages.items():
                    if s_name.lower() == stage_name.lower():
                        return s_config

        # Try default pipeline
        default_pipeline = self.pipelines.get("default", {})
        stages = default_pipeline.get("stages", {})
        return stages.get(stage_name)

    def reload(self):
        """Reload configuration from file."""
        self._load_config()


class GHLToTripleWhaleTransformer:
    """
    Transform GoHighLevel webhooks to Triple Whale events.

    Uses configurable pipeline mappings to determine event types
    and calculate attributed values.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize transformer.

        Args:
            config: Pipeline configuration. Loads default if not provided.
        """
        self.config = config or PipelineConfig()

    def transform(
        self,
        payload: GHLWebhookPayload,
    ) -> Optional[TripleWhaleEvent]:
        """
        Transform GHL webhook payload to Triple Whale event.

        Args:
            payload: GoHighLevel webhook payload

        Returns:
            TripleWhaleEvent or None if transformation not possible
        """
        # Validate we have customer identifier
        email = normalize_email(payload.email)
        phone = normalize_phone(payload.phone)

        if not email and not phone:
            logger.warning(
                f"Cannot transform event: no email or phone. "
                f"Contact ID: {payload.contact_id}"
            )
            return None

        # Determine event type from pipeline stage
        event_type, stage_config = self._determine_event_type(payload)

        if event_type is None:
            logger.debug(
                f"No mapping for stage '{payload.pipeline_stage}' "
                f"in pipeline '{payload.pipeline_name}'"
            )
            if not self.config.settings.get("send_unmapped_stages", True):
                return None
            event_type = TripleWhaleEventType.CUSTOM

        # Build properties
        properties = self._build_properties(payload, stage_config)

        # Calculate timestamp
        timestamp = self._get_timestamp(payload)

        # Create event
        event = TripleWhaleEvent(
            type=event_type,
            email=email,
            phone=phone,
            timestamp=timestamp,
            properties=properties,
        )

        logger.info(
            f"Transformed GHL event to Triple Whale: "
            f"type={event_type.value}, email={email or 'N/A'}"
        )

        return event

    def transform_contact_event(
        self,
        payload: GHLWebhookPayload,
        trigger_tag: Optional[str] = None,
    ) -> Optional[TripleWhaleEvent]:
        """
        Transform a contact-based event (tag added, source, etc.).

        Args:
            payload: GoHighLevel webhook payload
            trigger_tag: Tag that triggered the event (if applicable)

        Returns:
            TripleWhaleEvent or None
        """
        email = normalize_email(payload.email)
        phone = normalize_phone(payload.phone)

        if not email and not phone:
            return None

        # Check for tag-based mapping
        tag_config = None
        if trigger_tag:
            tag_mappings = self.config.contact_events.get("tags", {})
            tag_config = tag_mappings.get(trigger_tag)

        # Determine event type
        if tag_config:
            event_type_str = tag_config.get("event_type", "custom")
            try:
                event_type = TripleWhaleEventType(event_type_str)
            except ValueError:
                event_type = TripleWhaleEventType.CUSTOM
        else:
            event_type = TripleWhaleEventType.LEAD

        # Build properties
        properties = TripleWhaleEventProperties(
            source=payload.effective_source,
            ghl_contact_id=payload.contact_id,
            company_name=payload.company_name,
        )

        # Add tag config properties
        if tag_config:
            extra_props = tag_config.get("properties", {})
            for key, value in extra_props.items():
                setattr(properties, key, value)

            # Handle custom event name
            if tag_config.get("custom_event_name"):
                properties.event_name = tag_config["custom_event_name"]

        return TripleWhaleEvent(
            type=event_type,
            email=email,
            phone=phone,
            timestamp=self._get_timestamp(payload),
            properties=properties,
        )

    def _determine_event_type(
        self,
        payload: GHLWebhookPayload,
    ) -> tuple[Optional[TripleWhaleEventType], Optional[dict]]:
        """
        Determine Triple Whale event type from GHL payload.

        Returns:
            Tuple of (event_type, stage_config)
        """
        pipeline_name = payload.pipeline_name
        stage_name = payload.pipeline_stage

        if not pipeline_name or not stage_name:
            return None, None

        stage_config = self.config.get_stage_mapping(pipeline_name, stage_name)

        if not stage_config:
            # Use default event type
            default_type = self.config.settings.get("default_event_type", "custom")
            try:
                return TripleWhaleEventType(default_type), None
            except ValueError:
                return TripleWhaleEventType.CUSTOM, None

        # Get event type from config
        event_type_str = stage_config.get("event_type", "custom")
        try:
            event_type = TripleWhaleEventType(event_type_str)
        except ValueError:
            logger.warning(f"Unknown event type '{event_type_str}', using 'custom'")
            event_type = TripleWhaleEventType.CUSTOM

        return event_type, stage_config

    def _build_properties(
        self,
        payload: GHLWebhookPayload,
        stage_config: Optional[dict],
    ) -> TripleWhaleEventProperties:
        """
        Build event properties from payload and config.

        Args:
            payload: GHL webhook payload
            stage_config: Stage configuration from pipeline mapping

        Returns:
            TripleWhaleEventProperties
        """
        properties = TripleWhaleEventProperties(
            # Pipeline context
            pipeline_name=payload.pipeline_name,
            pipeline_stage=payload.pipeline_stage,
            opportunity_name=payload.opportunity_name,
            opportunity_id=payload.effective_opportunity_id,

            # CRM context
            ghl_contact_id=payload.contact_id,
            ghl_opportunity_id=payload.effective_opportunity_id,
            assigned_to=payload.assigned_to,
            company_name=payload.company_name if self.config.settings.get(
                "include_company_name", True
            ) else None,

            # Source
            source=payload.effective_source,

            # Currency
            currency=self.config.settings.get("default_currency", "USD"),
        )

        # Calculate value
        raw_value = payload.effective_value
        if raw_value and stage_config:
            multiplier = stage_config.get("value_multiplier", 1.0)
            calc_method = self.config.value_rules.get("calculation_method", "actual")

            if calc_method == "weighted":
                properties.lead_value = raw_value * multiplier
                properties.value = raw_value * multiplier
            elif calc_method == "fixed":
                event_type = stage_config.get("event_type", "custom")
                fixed_values = self.config.value_rules.get("fixed_values", {})
                properties.value = fixed_values.get(event_type, 0)
            else:  # actual
                properties.lead_value = raw_value
                properties.value = raw_value

            # Include revenue for closed won stages
            if stage_config.get("include_revenue"):
                properties.value = raw_value

        elif raw_value:
            properties.lead_value = raw_value
            properties.value = raw_value

        # Calculate days in pipeline
        if self.config.settings.get("calculate_days_in_pipeline") and payload.date_added:
            days = calculate_days_between(payload.date_added)
            if days is not None:
                properties.days_in_pipeline = days

        # Handle custom event name
        if stage_config and stage_config.get("custom_event_name"):
            properties.event_name = stage_config["custom_event_name"]

        # Map custom fields
        custom_field_mappings = self.config.field_mappings.get("custom_fields", {})
        for field in payload.custom_fields:
            key = field.key or field.id
            if key in custom_field_mappings:
                prop_name = custom_field_mappings[key]
                value = field.field_value or field.value
                if hasattr(properties, prop_name):
                    setattr(properties, prop_name, value)

        return properties

    def _get_timestamp(self, payload: GHLWebhookPayload) -> str:
        """Get timestamp for event."""
        ts = payload.timestamp or payload.date_updated or datetime.utcnow()

        if isinstance(ts, datetime):
            return ts.isoformat() + "Z"
        return str(ts)


# =============================================================================
# Convenience Functions
# =============================================================================

def transform_ghl_to_triple_whale(
    payload: dict[str, Any],
    config_path: Optional[str] = None,
) -> Optional[TripleWhaleEvent]:
    """
    Convenience function to transform a GHL webhook to Triple Whale event.

    Args:
        payload: Raw GHL webhook payload dict
        config_path: Optional path to pipeline config

    Returns:
        TripleWhaleEvent or None
    """
    ghl_payload = GHLWebhookPayload(**payload)

    config = PipelineConfig(config_path) if config_path else None
    transformer = GHLToTripleWhaleTransformer(config)

    return transformer.transform(ghl_payload)
