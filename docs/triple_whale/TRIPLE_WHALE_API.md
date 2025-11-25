# Triple Whale API Integration Guide

Complete guide for integrating Triple Whale's Data-In API with your tracking infrastructure, including strategic integration with GoHighLevel CRM for full-funnel attribution.

## Overview

Triple Whale's Data-In API enables businesses to:
- Send order/revenue data from custom sales platforms
- Track offline conversion events (leads, MQLs, SQLs, opportunities)
- Enrich existing data from native integrations
- Enable full customer journey attribution

```
┌─────────────────────────────────────────────────────────────────┐
│                    Triple Whale Data Flow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Triple      │    │  Data-In     │    │  3rd Party   │      │
│  │  Pixel       │    │  API         │    │  Integrations│      │
│  │  (Frontend)  │    │  (Backend)   │    │  (Ads, etc)  │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             ▼                                   │
│                   ┌──────────────────┐                          │
│                   │  Triple Whale    │                          │
│                   │  Attribution     │                          │
│                   │  Engine          │                          │
│                   └──────────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Authentication

### API Key Setup

1. Navigate to **Settings > API Keys** in Triple Whale dashboard
2. Click **Generate an API Key**
3. Select required scopes:
   - `Orders: Write` - For order data
   - `Products: Write` - For product catalog
   - `Subscriptions: Write` - For recurring billing
   - `Ads: Write` - For custom ad data
   - `PPS: Write` - For post-purchase surveys

4. Store the key securely (only shown once)

### Authentication Header

```bash
curl -X POST https://api.triplewhale.com/api/v2/data-in/orders \
  -H "x-api-key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

### Validate API Key

```bash
curl https://api.triplewhale.com/api/v2/users/api-keys/me \
  -H "x-api-key: YOUR_API_KEY"
```

## Core Endpoints

### Base URL
```
https://api.triplewhale.com/api/v2/data-in/
```

### Rate Limits
| Endpoint Type | Limit |
|--------------|-------|
| Data-In (orders, products, subscriptions) | 25,000 requests/minute |
| Pixel Events | 1,000 events/minute |
| Max payload (events) | 3 KB |

### Available Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/orders` | POST | Create/update order records |
| `/products` | POST | Create/update product catalog |
| `/subscriptions` | POST | Create/update subscription data |
| `/event` | POST | Send offline attribution events |

## Data-In Use Cases

### 1. Custom Sales Platform

For platforms without native Triple Whale integration (non-Shopify/WooCommerce/BigCommerce):

**Orders Endpoint** - `/orders`
```json
{
  "shop": "yourstore.com",
  "order_id": "ORD-12345",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "platform": "CUSTOM",
  "platform_account_id": "your_account_id",
  "customer": {
    "email": "customer@example.com",
    "phone": "+15551234567",
    "first_name": "John",
    "last_name": "Doe"
  },
  "line_items": [
    {
      "product_id": "PROD-001",
      "variant_id": "VAR-001",
      "quantity": 2,
      "price": 49.99
    }
  ],
  "total_price": 99.98,
  "subtotal_price": 99.98,
  "total_tax": 0,
  "total_discounts": 0,
  "currency": "USD"
}
```

### 2. Offline Attribution Events

**The critical endpoint for CRM integration:**

```
POST https://api.triplewhale.com/api/v2/data-in/event
```

**Supported Event Types:**
- `lead` - Initial lead capture
- `mql` - Marketing Qualified Lead
- `sql` - Sales Qualified Lead
- `opportunity` - Deal/opportunity created
- `book_demo` - Demo scheduled
- `custom` - Any custom conversion

**Example: Lead Event**
```json
{
  "type": "lead",
  "email": "prospect@company.com",
  "phone": "+15551234567",
  "timestamp": "2024-01-15T10:30:00Z",
  "properties": {
    "source": "landing_page",
    "campaign": "q1_promo",
    "lead_value": 500
  }
}
```

**Example: SQL Event**
```json
{
  "type": "sql",
  "email": "prospect@company.com",
  "timestamp": "2024-01-20T14:00:00Z",
  "properties": {
    "pipeline_stage": "Qualified",
    "deal_value": 5000,
    "sales_rep": "Jane Smith",
    "days_in_pipeline": 5
  }
}
```

### 3. Data Enrichment

For stores with native integrations (Shopify, etc.), enrich existing records:

- Add shipping costs
- Include custom tags
- Add product cost data for margin calculations

**Note:** Enrichment endpoints only work with native platform integrations.

## GoHighLevel CRM Integration

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GoHighLevel CRM                             │
├─────────────────────────────────────────────────────────────────┤
│  Pipeline Stage Changes  →  Outbound Webhook                    │
│  Contact Created         →  Outbound Webhook                    │
│  Opportunity Updates     →  Outbound Webhook                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│               Integration Middleware                            │
├─────────────────────────────────────────────────────────────────┤
│  • Receive GHL webhook payload                                  │
│  • Transform to Triple Whale format                             │
│  • Map pipeline stages → event types                            │
│  • POST to /event endpoint                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Triple Whale Attribution                       │
├─────────────────────────────────────────────────────────────────┤
│  • Links offline conversions to ad spend                        │
│  • Full customer journey visualization                          │
│  • ROAS on lead → customer lifecycle                            │
└─────────────────────────────────────────────────────────────────┘
```

### Pipeline Stage Mapping

| GHL Pipeline Stage | Triple Whale Event | Recommended Value |
|--------------------|-------------------|-------------------|
| New Lead | `lead` | $0 (potential) |
| Marketing Qualified | `mql` | Estimated pipeline value |
| Sales Qualified | `sql` | Weighted deal value |
| Demo Scheduled | `book_demo` | -- |
| Proposal Sent | `opportunity` | Deal amount |
| Closed Won | `custom:closed_won` | Actual revenue |

### GoHighLevel Webhook Setup

1. **Create Workflow Trigger**
   - Trigger: Pipeline Stage Changed
   - This ensures opportunity data is included in payload

2. **Add Webhook Action**
   - Method: POST
   - URL: Your integration endpoint
   - Authorization: Bearer token or API key

3. **Webhook Payload (GHL sends):**
```json
{
  "contact_id": "abc123",
  "email": "prospect@company.com",
  "phone": "+15551234567",
  "opportunity_name": "Enterprise Deal",
  "pipeline_name": "Main Sales",
  "pipeline_stage": "SQL",
  "lead_value": 10000,
  "status": "open",
  "source": "Facebook Ads"
}
```

### Integration Middleware Example

```python
from flask import Flask, request
import requests

app = Flask(__name__)

TRIPLE_WHALE_API_KEY = "your_api_key"
TRIPLE_WHALE_URL = "https://api.triplewhale.com/api/v2/data-in/event"

# Map GHL stages to Triple Whale event types
STAGE_MAPPING = {
    "New Lead": "lead",
    "Marketing Qualified": "mql",
    "Sales Qualified": "sql",
    "Demo Scheduled": "book_demo",
    "Proposal Sent": "opportunity",
    "Closed Won": "custom"
}

@app.route("/webhook/ghl", methods=["POST"])
def handle_ghl_webhook():
    data = request.json

    stage = data.get("pipeline_stage", "")
    event_type = STAGE_MAPPING.get(stage, "custom")

    triple_whale_payload = {
        "type": event_type,
        "email": data.get("email"),
        "phone": data.get("phone"),
        "timestamp": data.get("date_updated"),
        "properties": {
            "pipeline_name": data.get("pipeline_name"),
            "opportunity_name": data.get("opportunity_name"),
            "lead_value": data.get("lead_value", 0),
            "source": data.get("source"),
            "ghl_contact_id": data.get("contact_id")
        }
    }

    # Handle Closed Won as custom event with revenue
    if stage == "Closed Won":
        triple_whale_payload["properties"]["event_name"] = "closed_won"
        triple_whale_payload["properties"]["value"] = data.get("lead_value", 0)
        triple_whale_payload["properties"]["currency"] = "USD"

    response = requests.post(
        TRIPLE_WHALE_URL,
        headers={
            "x-api-key": TRIPLE_WHALE_API_KEY,
            "Content-Type": "application/json"
        },
        json=triple_whale_payload
    )

    return {"status": "success", "triple_whale_status": response.status_code}

if __name__ == "__main__":
    app.run(port=3000)
```

## Triple Pixel Setup

For attribution to work, you need both:
1. **Frontend Pixel** - Captures customer journey
2. **Backend API** - Confirms actual conversions

### Pixel Installation

Add to `<head>` on all pages:

```html
<script>
!function(e,t,n,c,o,a,f){
  e[o]=e[o]||function(){(e[o].q=e[o].q||[]).push(arguments)},
  a=t.createElement(n),f=t.getElementsByTagName(n)[0],
  a.async=1,a.src="https://api.triplewhale.com/tw/pixel/v2/"+c+".js",
  f.parentNode.insertBefore(a,f)
}(window,document,"script","YOUR_SHOP_DOMAIN","TriplePixel");
TriplePixel('init', {TripleName: 'YOUR_SHOP_DOMAIN', plat: 'CUSTOM'});
</script>
```

### Verify Installation

In browser console:
```javascript
TriplePixel('State');
// Should return: "Ready"
```

### Track Custom Events (Frontend)

```javascript
// Lead form submission
TriplePixel('custom', 'lead_form_submit', {
  form_name: 'contact_form',
  page: window.location.pathname
});

// Demo booking
TriplePixel('custom', 'book_demo', {
  demo_type: 'product_demo',
  preferred_time: '2024-01-20T10:00:00Z'
});
```

## Attribution Flow

```
1. User clicks Facebook ad
   └─→ Triple Pixel captures click_id, session data

2. User submits lead form
   └─→ Pixel: TriplePixel('custom', 'lead_form_submit', {...})
   └─→ API: POST /event {type: "lead", email: "..."}

3. Sales qualifies lead (in GoHighLevel)
   └─→ GHL Webhook → Your Integration → POST /event {type: "sql", ...}

4. Deal closes
   └─→ GHL Webhook → POST /event {type: "custom", properties: {event_name: "closed_won", value: 5000}}

5. Triple Whale Attribution
   └─→ Links closed deal revenue back to original Facebook ad
   └─→ Full customer journey visible in dashboard
```

## Processing Times

| Data Age | Processing Time |
|----------|-----------------|
| Past 2 days | ~5 minutes |
| Older data | Up to 20 minutes |

## Best Practices

### 1. Event Timing
Send Pixel event **before** API event for maximum attribution accuracy.

### 2. Customer Identity
Always include `email` or `phone` - required for matching events to journeys.

### 3. Retry Logic
```python
import time

def send_with_retry(payload, max_retries=4):
    delays = [2, 4, 8, 16]  # Exponential backoff

    for attempt in range(max_retries):
        response = requests.post(TRIPLE_WHALE_URL, json=payload, headers=headers)

        if response.status_code == 200:
            return response
        elif response.status_code in [429, 500, 502, 503]:
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])
        else:
            break

    return response
```

### 4. Historical Backfill
For historical data migration:
- Batch requests (e.g., 100 records/day)
- Use `created_at` timestamps from original records
- Expect up to 20 minutes processing for older data

### 5. Update Strategy
To update existing records, re-submit with matching:
- `shop`
- `order_id`
- `created_at`
- `platform`
- `platform_account_id`

All other fields will be overwritten.

## Verification

### Check API Health
Monitor **Custom Account Health** page in Triple Whale dashboard.

### Query Data via SQL
```sql
-- Check recent orders
SELECT * FROM orders_table
WHERE created_at > now() - interval 7 day
ORDER BY created_at DESC
LIMIT 100;

-- Check custom events
SELECT * FROM custom_pixel_events_table
WHERE event_date > today() - 7
ORDER BY event_timestamp DESC;
```

## Troubleshooting

### Events Not Appearing
1. Verify API key has correct scopes
2. Check `email` or `phone` is included
3. Confirm timestamp format is ISO 8601
4. Check rate limits not exceeded

### Attribution Not Linking
1. Ensure Pixel is installed and returning "Ready"
2. Verify Pixel event fires before API event
3. Check customer identifier matches between Pixel and API

### Low Match Quality
1. Include both `email` and `phone` when available
2. Ensure consistent formatting (lowercase email, E.164 phone)
3. Add additional customer identifiers in properties

## Resources

- [Triple Whale API Documentation](https://triplewhale.readme.io/reference/introduction-to-the-triple-whale-api)
- [Data-In Use Cases](https://triplewhale.readme.io/reference/data-in-api-use-cases)
- [Custom Events Guide](https://kb.triplewhale.com/en/articles/9957947-tracking-custom-events-with-triple-pixel-attribution)
- [Triple Whale GitHub](https://github.com/Triple-Whale/triple-whale-public-apis)
- [GoHighLevel API Docs](https://marketplace.gohighlevel.com/docs/)
- [GoHighLevel Webhooks](https://help.gohighlevel.com/support/solutions/articles/155000003299-actions-webhook)

---

For implementation support, contact support@organized.ai
