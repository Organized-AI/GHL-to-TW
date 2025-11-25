"""
Pytest configuration and fixtures for Triple Whale Bridge tests.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Set test environment variables before importing app modules
os.environ.setdefault("TRIPLE_WHALE_API_KEY", "test_api_key_12345")


@pytest.fixture
def sample_ghl_opportunity_payload():
    """Sample GoHighLevel opportunity/pipeline webhook payload."""
    return {
        "type": "OpportunityStageUpdate",
        "locationId": "loc_123",
        "contactId": "contact_456",
        "email": "john.doe@example.com",
        "phone": "+15551234567",
        "firstName": "John",
        "lastName": "Doe",
        "companyName": "Acme Corp",
        "tags": ["lead-magnet", "enterprise"],
        "source": "facebook",
        "opportunityId": "opp_789",
        "opportunityName": "Enterprise Deal - Acme",
        "pipelineId": "pipe_001",
        "pipelineName": "Main Sales Pipeline",
        "pipelineStage": "Qualified",
        "status": "open",
        "leadValue": 10000,
        "monetaryValue": 10000,
        "assignedTo": "sales_rep_001",
        "dateAdded": "2024-01-01T10:00:00Z",
        "dateUpdated": "2024-01-15T14:30:00Z",
    }


@pytest.fixture
def sample_ghl_contact_payload():
    """Sample GoHighLevel contact webhook payload."""
    return {
        "type": "ContactCreate",
        "locationId": "loc_123",
        "contactId": "contact_789",
        "email": "jane.smith@example.com",
        "phone": "+15559876543",
        "firstName": "Jane",
        "lastName": "Smith",
        "companyName": "Tech Startup",
        "tags": ["demo-requested"],
        "source": "google",
        "attributionSource": "google_ads",
        "dateAdded": "2024-01-10T08:00:00Z",
    }


@pytest.fixture
def sample_ghl_closed_won_payload():
    """Sample GoHighLevel closed won webhook payload."""
    return {
        "type": "OpportunityStageUpdate",
        "contactId": "contact_456",
        "email": "john.doe@example.com",
        "phone": "+15551234567",
        "firstName": "John",
        "lastName": "Doe",
        "companyName": "Acme Corp",
        "opportunityId": "opp_789",
        "opportunityName": "Enterprise Deal - Acme",
        "pipelineName": "Main Sales Pipeline",
        "pipelineStage": "Closed Won",
        "status": "won",
        "leadValue": 50000,
        "monetaryValue": 50000,
        "dateAdded": "2024-01-01T10:00:00Z",
        "dateUpdated": "2024-02-01T16:00:00Z",
    }


@pytest.fixture
def sample_ghl_minimal_payload():
    """Minimal GoHighLevel payload with just required fields."""
    return {
        "email": "minimal@example.com",
        "pipelineName": "Main Sales Pipeline",
        "pipelineStage": "New Lead",
    }


@pytest.fixture
def mock_triple_whale_client():
    """Mock Triple Whale client for testing without API calls."""
    client = MagicMock()
    client.send_event = AsyncMock(return_value={"status": "success"})
    client.validate_api_key = AsyncMock(return_value={"valid": True})
    client.close = AsyncMock()
    return client


@pytest.fixture
def pipeline_config_dict():
    """Sample pipeline configuration dictionary."""
    return {
        "settings": {
            "default_currency": "USD",
            "send_unmapped_stages": True,
            "default_event_type": "custom",
            "include_company_name": True,
            "calculate_days_in_pipeline": True,
        },
        "pipelines": {
            "Main Sales Pipeline": {
                "stages": {
                    "New Lead": {
                        "event_type": "lead",
                        "value_multiplier": 0.0,
                    },
                    "Qualified": {
                        "event_type": "mql",
                        "value_multiplier": 0.10,
                    },
                    "Demo Scheduled": {
                        "event_type": "book_demo",
                        "value_multiplier": 0.25,
                    },
                    "Proposal Sent": {
                        "event_type": "opportunity",
                        "value_multiplier": 0.50,
                    },
                    "Closed Won": {
                        "event_type": "custom",
                        "custom_event_name": "closed_won",
                        "value_multiplier": 1.0,
                        "include_revenue": True,
                    },
                }
            }
        },
        "value_rules": {
            "calculation_method": "weighted",
        },
    }
