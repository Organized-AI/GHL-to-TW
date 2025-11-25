"""Tests for GHL to Triple Whale transformers."""

import pytest
from unittest.mock import patch, MagicMock

from triple_whale_bridge.core.schema import (
    GHLWebhookPayload,
    TripleWhaleEventType,
)
from triple_whale_bridge.core.transformers import (
    GHLToTripleWhaleTransformer,
    PipelineConfig,
)


class TestPipelineConfig:
    """Tests for pipeline configuration loading."""

    def test_default_config_loads(self):
        """Test default configuration loads without errors."""
        # Use mock to avoid file system dependency
        with patch.object(PipelineConfig, '_load_config') as mock_load:
            mock_load.return_value = None
            config = PipelineConfig()
            config._config = config._get_default_config()

            assert "pipelines" in config._config
            assert "settings" in config._config

    def test_get_stage_mapping(self, pipeline_config_dict):
        """Test getting stage mapping from config."""
        config = PipelineConfig()
        config._config = pipeline_config_dict

        mapping = config.get_stage_mapping("Main Sales Pipeline", "Qualified")

        assert mapping is not None
        assert mapping["event_type"] == "mql"
        assert mapping["value_multiplier"] == 0.10

    def test_get_stage_mapping_case_insensitive(self, pipeline_config_dict):
        """Test stage mapping is case insensitive."""
        config = PipelineConfig()
        config._config = pipeline_config_dict

        # Different case should still work
        mapping = config.get_stage_mapping("main sales pipeline", "qualified")

        assert mapping is not None
        assert mapping["event_type"] == "mql"

    def test_get_stage_mapping_not_found(self, pipeline_config_dict):
        """Test behavior when stage not found."""
        config = PipelineConfig()
        config._config = pipeline_config_dict

        mapping = config.get_stage_mapping("Unknown Pipeline", "Unknown Stage")

        assert mapping is None


class TestGHLToTripleWhaleTransformer:
    """Tests for the GHL to Triple Whale transformer."""

    @pytest.fixture
    def transformer(self, pipeline_config_dict):
        """Create transformer with test config."""
        config = PipelineConfig()
        config._config = pipeline_config_dict
        return GHLToTripleWhaleTransformer(config)

    def test_transform_opportunity_to_mql(
        self,
        transformer,
        sample_ghl_opportunity_payload
    ):
        """Test transforming qualified lead to MQL event."""
        payload = GHLWebhookPayload(**sample_ghl_opportunity_payload)
        event = transformer.transform(payload)

        assert event is not None
        assert event.type == TripleWhaleEventType.MQL
        assert event.email == "john.doe@example.com"
        assert event.phone == "+15551234567"
        assert event.properties.pipeline_name == "Main Sales Pipeline"
        assert event.properties.pipeline_stage == "Qualified"
        assert event.properties.company_name == "Acme Corp"

    def test_transform_closed_won(
        self,
        transformer,
        sample_ghl_closed_won_payload
    ):
        """Test transforming closed won to custom event with revenue."""
        payload = GHLWebhookPayload(**sample_ghl_closed_won_payload)
        event = transformer.transform(payload)

        assert event is not None
        assert event.type == TripleWhaleEventType.CUSTOM
        assert event.properties.event_name == "closed_won"
        assert event.properties.value == 50000  # Full value for closed won

    def test_transform_new_lead(self, transformer, sample_ghl_minimal_payload):
        """Test transforming new lead."""
        payload = GHLWebhookPayload(**sample_ghl_minimal_payload)
        event = transformer.transform(payload)

        assert event is not None
        assert event.type == TripleWhaleEventType.LEAD
        assert event.email == "minimal@example.com"

    def test_transform_missing_identifier_returns_none(self, transformer):
        """Test that missing email/phone returns None."""
        payload = GHLWebhookPayload(
            pipelineName="Main Sales Pipeline",
            pipelineStage="Qualified",
        )
        event = transformer.transform(payload)

        assert event is None

    def test_transform_unmapped_stage(self, transformer):
        """Test transforming unmapped stage uses default type."""
        payload = GHLWebhookPayload(
            email="test@example.com",
            pipelineName="Main Sales Pipeline",
            pipelineStage="Unknown Stage",
        )
        event = transformer.transform(payload)

        assert event is not None
        assert event.type == TripleWhaleEventType.CUSTOM

    def test_transform_calculates_days_in_pipeline(
        self,
        transformer,
        sample_ghl_opportunity_payload
    ):
        """Test days in pipeline calculation."""
        payload = GHLWebhookPayload(**sample_ghl_opportunity_payload)
        event = transformer.transform(payload)

        # dateAdded was 2024-01-01, should have some days calculated
        assert event.properties.days_in_pipeline is not None
        assert event.properties.days_in_pipeline >= 0

    def test_transform_weighted_value_calculation(
        self,
        transformer,
        sample_ghl_opportunity_payload
    ):
        """Test weighted value calculation."""
        payload = GHLWebhookPayload(**sample_ghl_opportunity_payload)
        event = transformer.transform(payload)

        # Qualified stage has 0.10 multiplier, lead_value is 10000
        # So attributed value should be 1000
        assert event.properties.lead_value == 1000
        assert event.properties.value == 1000

    def test_transform_normalizes_email(self, transformer):
        """Test email is normalized (lowercase, trimmed)."""
        payload = GHLWebhookPayload(
            email="  Test.User@EXAMPLE.com  ",
            pipelineName="Main Sales Pipeline",
            pipelineStage="New Lead",
        )
        event = transformer.transform(payload)

        assert event.email == "test.user@example.com"

    def test_transform_normalizes_phone(self, transformer):
        """Test phone is normalized to E.164."""
        payload = GHLWebhookPayload(
            phone="(555) 123-4567",
            pipelineName="Main Sales Pipeline",
            pipelineStage="New Lead",
        )
        event = transformer.transform(payload)

        assert event.phone == "+15551234567"

    def test_transform_contact_event(
        self,
        transformer,
        sample_ghl_contact_payload
    ):
        """Test transforming contact event with tag."""
        # Add tag mapping to config
        transformer.config._config["contact_events"] = {
            "tags": {
                "demo-requested": {
                    "event_type": "book_demo",
                    "properties": {"source": "demo_request"}
                }
            }
        }

        payload = GHLWebhookPayload(**sample_ghl_contact_payload)
        event = transformer.transform_contact_event(payload, trigger_tag="demo-requested")

        assert event is not None
        assert event.type == TripleWhaleEventType.BOOK_DEMO
        assert event.properties.source == "demo_request"
