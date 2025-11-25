"""
Pydantic models for GoHighLevel webhooks and Triple Whale events.

These schemas define the data structures for:
- Incoming GHL webhook payloads (contacts, opportunities, pipeline changes)
- Outgoing Triple Whale attribution events
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Triple Whale Event Types
# =============================================================================

class TripleWhaleEventType(str, Enum):
    """Supported Triple Whale offline attribution event types."""
    LEAD = "lead"
    MQL = "mql"  # Marketing Qualified Lead
    SQL = "sql"  # Sales Qualified Lead
    OPPORTUNITY = "opportunity"
    BOOK_DEMO = "book_demo"
    CUSTOM = "custom"


# =============================================================================
# GoHighLevel Webhook Models
# =============================================================================

class GHLCustomField(BaseModel):
    """Custom field from GoHighLevel."""
    id: Optional[str] = None
    key: Optional[str] = None
    field_value: Optional[Any] = Field(None, alias="fieldValue")
    value: Optional[Any] = None

    class Config:
        populate_by_name = True


class GHLContact(BaseModel):
    """GoHighLevel contact data from webhook payload."""
    id: str = Field(..., description="GHL contact ID")
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    full_name: Optional[str] = Field(None, alias="fullName")
    name: Optional[str] = None
    company_name: Optional[str] = Field(None, alias="companyName")
    website: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    address1: Optional[str] = None
    postal_code: Optional[str] = Field(None, alias="postalCode")
    date_added: Optional[datetime] = Field(None, alias="dateAdded")
    date_updated: Optional[datetime] = Field(None, alias="dateUpdated")
    custom_fields: list[GHLCustomField] = Field(default_factory=list, alias="customFields")
    attribution_source: Optional[str] = Field(None, alias="attributionSource")

    class Config:
        populate_by_name = True

    @property
    def display_name(self) -> str:
        """Get best available name for contact."""
        if self.full_name:
            return self.full_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        if self.name:
            return self.name
        return self.email or self.id


class GHLOpportunity(BaseModel):
    """GoHighLevel opportunity/deal data from webhook payload."""
    id: str = Field(..., description="GHL opportunity ID")
    name: Optional[str] = Field(None, alias="opportunity_name")
    opportunity_name: Optional[str] = Field(None, alias="opportunityName")
    status: Optional[str] = None
    pipeline_id: Optional[str] = Field(None, alias="pipelineId")
    pipeline_name: Optional[str] = Field(None, alias="pipelineName")
    pipeline_stage: Optional[str] = Field(None, alias="pipelineStage")
    pipeline_stage_id: Optional[str] = Field(None, alias="pipelineStageId")
    lead_value: Optional[float] = Field(None, alias="leadValue")
    monetary_value: Optional[float] = Field(None, alias="monetaryValue")
    source: Optional[str] = None
    opportunity_source: Optional[str] = Field(None, alias="opportunitySource")
    assigned_to: Optional[str] = Field(None, alias="assignedTo")
    contact_id: Optional[str] = Field(None, alias="contactId")
    date_added: Optional[datetime] = Field(None, alias="dateAdded")
    date_updated: Optional[datetime] = Field(None, alias="dateUpdated")

    class Config:
        populate_by_name = True

    @property
    def display_name(self) -> str:
        """Get opportunity name."""
        return self.opportunity_name or self.name or self.id

    @property
    def value(self) -> float:
        """Get monetary value of opportunity."""
        return self.monetary_value or self.lead_value or 0.0


class GHLWebhookPayload(BaseModel):
    """
    Complete GoHighLevel webhook payload.

    GHL sends different data depending on the workflow trigger:
    - Contact triggers: Full contact data
    - Opportunity triggers: Full opportunity + contact data
    - Pipeline stage change: Opportunity data with stage info
    """
    # Event metadata
    type: Optional[str] = None  # e.g., "ContactCreate", "OpportunityStageUpdate"
    location_id: Optional[str] = Field(None, alias="locationId")
    workflow_id: Optional[str] = Field(None, alias="workflowId")
    workflow_name: Optional[str] = Field(None, alias="workflowName")

    # Contact data (always present for contact-related events)
    contact_id: Optional[str] = Field(None, alias="contactId")
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    full_name: Optional[str] = Field(None, alias="fullName")
    name: Optional[str] = None
    company_name: Optional[str] = Field(None, alias="companyName")
    tags: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    attribution_source: Optional[str] = Field(None, alias="attributionSource")
    custom_fields: list[GHLCustomField] = Field(default_factory=list, alias="customFields")

    # Opportunity data (present for pipeline/opportunity events)
    opportunity_id: Optional[str] = Field(None, alias="opportunityId")
    id: Optional[str] = None  # Sometimes opportunity ID comes as 'id'
    opportunity_name: Optional[str] = Field(None, alias="opportunityName")
    pipeline_id: Optional[str] = Field(None, alias="pipelineId")
    pipeline_name: Optional[str] = Field(None, alias="pipelineName")
    pipeline_stage: Optional[str] = Field(None, alias="pipelineStage")
    pipeline_stage_id: Optional[str] = Field(None, alias="pipelineStageId")
    status: Optional[str] = None
    lead_value: Optional[float] = Field(None, alias="leadValue")
    monetary_value: Optional[float] = Field(None, alias="monetaryValue")
    opportunity_source: Optional[str] = Field(None, alias="opportunitySource")
    assigned_to: Optional[str] = Field(None, alias="assignedTo")

    # Timestamps
    date_added: Optional[datetime] = Field(None, alias="dateAdded")
    date_updated: Optional[datetime] = Field(None, alias="dateUpdated")
    timestamp: Optional[datetime] = None

    class Config:
        populate_by_name = True
        extra = "allow"  # Allow additional fields from GHL

    @field_validator("lead_value", "monetary_value", mode="before")
    @classmethod
    def parse_monetary_value(cls, v):
        """Parse monetary values that may come as strings."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return float(v.replace(",", "").replace("$", ""))
            except ValueError:
                return None
        return float(v)

    @property
    def effective_contact_id(self) -> Optional[str]:
        """Get the contact ID from various possible fields."""
        return self.contact_id

    @property
    def effective_opportunity_id(self) -> Optional[str]:
        """Get the opportunity ID from various possible fields."""
        return self.opportunity_id or self.id

    @property
    def effective_value(self) -> float:
        """Get the monetary value from available fields."""
        return self.monetary_value or self.lead_value or 0.0

    @property
    def effective_source(self) -> Optional[str]:
        """Get attribution source from available fields."""
        return self.attribution_source or self.opportunity_source or self.source


# =============================================================================
# Triple Whale Event Models
# =============================================================================

class TripleWhaleEventProperties(BaseModel):
    """
    Custom properties for Triple Whale events.

    These appear in attribution dashboards and can be queried via SQL.
    """
    # Pipeline context
    pipeline_name: Optional[str] = None
    pipeline_stage: Optional[str] = None
    opportunity_name: Optional[str] = None
    opportunity_id: Optional[str] = None

    # Value tracking
    lead_value: Optional[float] = None
    value: Optional[float] = None  # For custom conversion value
    currency: str = "USD"

    # Attribution context
    source: Optional[str] = None
    campaign: Optional[str] = None
    medium: Optional[str] = None

    # CRM context
    ghl_contact_id: Optional[str] = None
    ghl_opportunity_id: Optional[str] = None
    assigned_to: Optional[str] = None
    company_name: Optional[str] = None

    # Timing
    days_in_pipeline: Optional[int] = None

    # Custom event name (for type=custom)
    event_name: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional custom properties


class TripleWhaleEvent(BaseModel):
    """
    Triple Whale offline attribution event.

    Sent to: POST https://api.triplewhale.com/api/v2/data-in/event

    Required: type + (email OR phone)
    """
    type: TripleWhaleEventType = Field(
        ...,
        description="Event type for attribution"
    )
    email: Optional[str] = Field(
        None,
        description="Customer email (required if no phone)"
    )
    phone: Optional[str] = Field(
        None,
        description="Customer phone in E.164 format (required if no email)"
    )
    timestamp: Optional[str] = Field(
        None,
        description="ISO 8601 timestamp of the event"
    )
    properties: TripleWhaleEventProperties = Field(
        default_factory=TripleWhaleEventProperties,
        description="Custom event properties"
    )

    @field_validator("timestamp", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        """Ensure timestamp is ISO 8601 formatted string."""
        if v is None:
            return datetime.utcnow().isoformat() + "Z"
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v

    def model_dump_for_api(self) -> dict:
        """
        Prepare payload for Triple Whale API.

        Returns dict suitable for JSON serialization to the API.
        """
        data = {
            "type": self.type.value,
            "timestamp": self.timestamp,
            "properties": {
                k: v for k, v in self.properties.model_dump().items()
                if v is not None
            }
        }

        # Include identifier (email or phone required)
        if self.email:
            data["email"] = self.email.lower().strip()
        if self.phone:
            data["phone"] = self.phone

        return data


# =============================================================================
# API Response Models
# =============================================================================

class WebhookResponse(BaseModel):
    """Response from webhook endpoint."""
    success: bool
    message: str
    event_type: Optional[str] = None
    triple_whale_status: Optional[int] = None
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Response from health check endpoint."""
    status: str
    version: str
    triple_whale_configured: bool
    timestamp: str
