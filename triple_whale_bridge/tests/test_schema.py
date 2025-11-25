"""Tests for Pydantic schema models."""

import pytest
from datetime import datetime

from triple_whale_bridge.core.schema import (
    GHLWebhookPayload,
    GHLContact,
    GHLOpportunity,
    TripleWhaleEvent,
    TripleWhaleEventType,
    TripleWhaleEventProperties,
)


class TestGHLWebhookPayload:
    """Tests for GoHighLevel webhook payload parsing."""

    def test_parse_opportunity_payload(self, sample_ghl_opportunity_payload):
        """Test parsing a full opportunity payload."""
        payload = GHLWebhookPayload(**sample_ghl_opportunity_payload)

        assert payload.email == "john.doe@example.com"
        assert payload.phone == "+15551234567"
        assert payload.pipeline_name == "Main Sales Pipeline"
        assert payload.pipeline_stage == "Qualified"
        assert payload.lead_value == 10000
        assert payload.company_name == "Acme Corp"

    def test_parse_contact_payload(self, sample_ghl_contact_payload):
        """Test parsing a contact webhook payload."""
        payload = GHLWebhookPayload(**sample_ghl_contact_payload)

        assert payload.email == "jane.smith@example.com"
        assert payload.attribution_source == "google_ads"
        assert "demo-requested" in payload.tags

    def test_parse_minimal_payload(self, sample_ghl_minimal_payload):
        """Test parsing minimal payload."""
        payload = GHLWebhookPayload(**sample_ghl_minimal_payload)

        assert payload.email == "minimal@example.com"
        assert payload.pipeline_stage == "New Lead"
        assert payload.phone is None

    def test_monetary_value_parsing(self):
        """Test parsing monetary values in different formats."""
        # String with comma
        payload = GHLWebhookPayload(
            email="test@example.com",
            leadValue="10,000"
        )
        assert payload.lead_value == 10000

        # String with dollar sign
        payload = GHLWebhookPayload(
            email="test@example.com",
            monetaryValue="$5,000.50"
        )
        assert payload.monetary_value == 5000.50

    def test_effective_value_property(self, sample_ghl_opportunity_payload):
        """Test effective_value returns correct value."""
        payload = GHLWebhookPayload(**sample_ghl_opportunity_payload)
        assert payload.effective_value == 10000

        # Prefer monetary_value over lead_value
        payload.monetary_value = 15000
        assert payload.effective_value == 15000

    def test_extra_fields_allowed(self):
        """Test that extra fields from GHL don't break parsing."""
        payload = GHLWebhookPayload(
            email="test@example.com",
            unknownField="should not break",
            anotherUnknown={"nested": "value"}
        )
        assert payload.email == "test@example.com"


class TestTripleWhaleEvent:
    """Tests for Triple Whale event model."""

    def test_create_lead_event(self):
        """Test creating a lead event."""
        event = TripleWhaleEvent(
            type=TripleWhaleEventType.LEAD,
            email="test@example.com",
            properties=TripleWhaleEventProperties(
                source="facebook",
                pipeline_name="Sales Pipeline"
            )
        )

        assert event.type == TripleWhaleEventType.LEAD
        assert event.email == "test@example.com"
        assert event.properties.source == "facebook"

    def test_create_event_with_phone(self):
        """Test creating event with phone only."""
        event = TripleWhaleEvent(
            type=TripleWhaleEventType.SQL,
            phone="+15551234567",
        )

        assert event.phone == "+15551234567"
        assert event.email is None

    def test_model_dump_for_api(self):
        """Test API payload generation."""
        event = TripleWhaleEvent(
            type=TripleWhaleEventType.MQL,
            email="Test@Example.com",
            phone="+15551234567",
            properties=TripleWhaleEventProperties(
                pipeline_name="Sales",
                lead_value=5000,
                source=None,  # Should be excluded
            )
        )

        payload = event.model_dump_for_api()

        assert payload["type"] == "mql"
        assert payload["email"] == "test@example.com"  # Lowercased
        assert payload["phone"] == "+15551234567"
        assert "source" not in payload["properties"]  # None excluded
        assert payload["properties"]["pipeline_name"] == "Sales"

    def test_timestamp_formatting(self):
        """Test timestamp is properly formatted."""
        event = TripleWhaleEvent(
            type=TripleWhaleEventType.LEAD,
            email="test@example.com",
            timestamp=datetime(2024, 1, 15, 10, 30, 0)
        )

        assert "2024-01-15" in event.timestamp
        assert event.timestamp.endswith("Z")

    def test_auto_timestamp(self):
        """Test automatic timestamp generation."""
        event = TripleWhaleEvent(
            type=TripleWhaleEventType.LEAD,
            email="test@example.com",
        )

        assert event.timestamp is not None
        assert "Z" in event.timestamp


class TestTripleWhaleEventType:
    """Tests for event type enum."""

    def test_all_event_types_valid(self):
        """Test all event types are valid."""
        assert TripleWhaleEventType.LEAD.value == "lead"
        assert TripleWhaleEventType.MQL.value == "mql"
        assert TripleWhaleEventType.SQL.value == "sql"
        assert TripleWhaleEventType.OPPORTUNITY.value == "opportunity"
        assert TripleWhaleEventType.BOOK_DEMO.value == "book_demo"
        assert TripleWhaleEventType.CUSTOM.value == "custom"

    def test_event_type_from_string(self):
        """Test creating event type from string."""
        assert TripleWhaleEventType("lead") == TripleWhaleEventType.LEAD
        assert TripleWhaleEventType("mql") == TripleWhaleEventType.MQL
