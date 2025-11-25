---
name: triple-whale-bridge
description: Transform GoHighLevel CRM webhook data into Triple Whale API format for /data-in/orders or /data-in/event endpoints. Use when sending GHL pipeline data to Triple Whale for attribution.
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Grep
  - Glob
---

# Triple Whale Bridge - GHL to Triple Whale Transformation

Transform GoHighLevel (GHL) CRM webhook data into Triple Whale API format for full-funnel marketing attribution.

## Activation Triggers

This skill activates when users:
- Ask to transform GHL webhook data for Triple Whale
- Need to send CRM pipeline events to Triple Whale
- Want to format data for `/data-in/event` or `/data-in/orders` endpoints
- Ask about GHL → Triple Whale integration

Example prompts:
- "Transform this GHL webhook for Triple Whale"
- "Send this pipeline data to Triple Whale"
- "Format this CRM event for Triple Whale attribution"
- "How do I map GHL stages to Triple Whale events?"

## Quick Reference

### Triple Whale API Endpoints

| Endpoint | Rate Limit | Use Case |
|----------|------------|----------|
| `POST /data-in/event` | 1,000/min | CRM attribution events |
| `POST /data-in/orders` | 25,000/min | Closed deals as orders |

**Base URL:** `https://api.triplewhale.com/api/v2`
**Auth Header:** `x-api-key: YOUR_API_KEY`

### Pipeline Stage → Event Type Mapping

| GHL Stage | TW Event | Value Attribution |
|-----------|----------|-------------------|
| New Lead | `lead` | 0% |
| Qualified | `mql` | 10% |
| Sales Qualified | `sql` | 25% |
| Demo Scheduled | `book_demo` | 20% |
| Proposal Sent | `opportunity` | 50% |
| Closed Won | `custom` | 100% |

## Core Transformation

### GHL Webhook → Triple Whale Event

**Input (GHL):**
```json
{
  "email": "customer@example.com",
  "phone": "+15551234567",
  "pipelineName": "Main Sales Pipeline",
  "pipelineStage": "Qualified",
  "opportunityId": "opp_123",
  "opportunityName": "Enterprise Deal",
  "leadValue": 10000,
  "source": "google_ads",
  "dateAdded": "2024-01-01T10:00:00Z",
  "dateUpdated": "2024-01-15T14:30:00Z"
}
```

**Output (Triple Whale):**
```json
{
  "type": "mql",
  "email": "customer@example.com",
  "phone": "+15551234567",
  "timestamp": "2024-01-15T14:30:00Z",
  "properties": {
    "pipeline_name": "Main Sales Pipeline",
    "pipeline_stage": "Qualified",
    "opportunity_name": "Enterprise Deal",
    "opportunity_id": "opp_123",
    "lead_value": 10000,
    "value": 1000,
    "currency": "USD",
    "source": "google_ads",
    "days_in_pipeline": 14
  }
}
```

### GHL Closed Won → Triple Whale Order

**Output (Triple Whale Order):**
```json
{
  "shop": "yourcompany.com",
  "order_id": "GHL-opp_123",
  "created_at": "2024-01-01T10:00:00Z",
  "platform": "CUSTOM",
  "customer": {
    "email": "customer@example.com",
    "phone": "+15551234567"
  },
  "line_items": [{
    "product_id": "enterprise_plan",
    "title": "Enterprise Deal",
    "quantity": 1,
    "price": 10000
  }],
  "total_price": 10000,
  "currency": "USD",
  "source_name": "gohighlevel"
}
```

## Required Fields

### For Events Endpoint
- `type` — Event type (lead, mql, sql, book_demo, opportunity, custom)
- `email` OR `phone` — At least one identifier

### For Orders Endpoint
- `shop` — Store domain
- `order_id` — Unique identifier
- `customer.email` OR `customer.phone`
- `line_items` — Array with product_id, quantity, price
- `total_price`

## Data Normalization Rules

### Phone Numbers → E.164
```
(555) 123-4567  →  +15551234567
555-123-4567    →  +15551234567
15551234567     →  +15551234567
```

### Email → Lowercase
```
John.Doe@Example.COM  →  john.doe@example.com
```

### Monetary Values → Number
```
"$10,000"  →  10000
"10,000"   →  10000
10000      →  10000
```

## Error Handling

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Event accepted |
| 401 | Invalid API key | Check TRIPLE_WHALE_API_KEY |
| 403 | Missing scope | Enable "Orders: Write" |
| 422 | Validation error | Check required fields |
| 429 | Rate limited | Retry with backoff (2s, 4s, 8s, 16s) |
| 5xx | Server error | Retry with backoff |

## Reference Materials

For complete documentation, see:

- **`references/ghl-webhook-fields.md`** — All GHL webhook fields
- **`references/triple-whale-api-reference.md`** — Complete API docs
- **`references/pipeline-stage-mappings.md`** — Stage mapping guide
- **`references/transformation-code.md`** — Python/JS implementations
- **`assets/ghl-webhook-template.md`** — GHL payload templates
- **`assets/triple-whale-payload-templates.md`** — TW payload templates

## Using the Bridge Service

The `triple_whale_bridge` service handles transformations automatically:

```bash
# Start the service
cd triple_whale_bridge
export TRIPLE_WHALE_API_KEY="your_key"
python -m triple_whale_bridge --port 8000

# Test transformation
curl -X POST http://localhost:8000/test/transform \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "pipelineStage": "Qualified"}'

# Configure GHL webhook URL
https://your-domain.com/webhook/ghl
```

## Attribution Requirements

For Triple Whale attribution to work:

1. **Triple Pixel installed** on your website
2. **Pixel event fires BEFORE API event**
3. **Email/phone matches** between Pixel and API
4. **Processing time:** ~5 min (recent) or ~20 min (historical)
