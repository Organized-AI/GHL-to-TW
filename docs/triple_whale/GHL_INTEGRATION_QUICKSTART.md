# GoHighLevel → Triple Whale Quick Start

Fast-track guide for connecting GoHighLevel CRM events to Triple Whale attribution.

## Prerequisites

- [ ] Triple Whale account with API access
- [ ] GoHighLevel account with workflow permissions
- [ ] Integration endpoint (serverless function, webhook relay, or custom server)

## Step 1: Create Triple Whale API Key

1. Go to **Settings > API Keys** in Triple Whale
2. Click **Generate an API Key**
3. Enable scope: `Orders: Write` (covers events)
4. Copy and save the key securely

## Step 2: Set Up GoHighLevel Workflow

### Create Workflow

1. **Automation > Workflows > Create Workflow**
2. Name: "Triple Whale Attribution Sync"

### Add Trigger

- **Trigger Type:** Pipeline Stage Changed
- **Pipeline:** Select your sales pipeline
- **Stages:** All stages (or specific stages you want to track)

### Add Webhook Action

- **Action Type:** Webhook (Outbound)
- **Method:** POST
- **URL:** `https://your-endpoint.com/webhook/ghl-to-triplewhale`
- **Headers:**
  ```
  Content-Type: application/json
  Authorization: Bearer YOUR_SECRET
  ```

## Step 3: Deploy Integration Endpoint

### Option A: Serverless (Recommended)

**AWS Lambda / Vercel / Cloudflare Workers:**

```javascript
// Vercel Edge Function Example
export default async function handler(req) {
  const data = await req.json();

  const stageMap = {
    "New Lead": "lead",
    "Qualified": "mql",
    "Sales Ready": "sql",
    "Demo Booked": "book_demo",
    "Proposal": "opportunity",
    "Closed Won": "custom"
  };

  const payload = {
    type: stageMap[data.pipeline_stage] || "custom",
    email: data.email,
    phone: data.phone,
    timestamp: new Date().toISOString(),
    properties: {
      pipeline_name: data.pipeline_name,
      stage: data.pipeline_stage,
      lead_value: data.lead_value || 0,
      opportunity_id: data.id
    }
  };

  // Add revenue for closed deals
  if (data.pipeline_stage === "Closed Won") {
    payload.properties.event_name = "closed_won";
    payload.properties.value = data.lead_value;
    payload.properties.currency = "USD";
  }

  const response = await fetch(
    "https://api.triplewhale.com/api/v2/data-in/event",
    {
      method: "POST",
      headers: {
        "x-api-key": process.env.TRIPLE_WHALE_API_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    }
  );

  return new Response(JSON.stringify({
    success: response.ok,
    status: response.status
  }));
}
```

### Option B: Make.com / Zapier

1. **Trigger:** Webhook (Custom)
2. **Transform:** Map GHL fields to Triple Whale format
3. **Action:** HTTP Request to Triple Whale API

## Step 4: Test the Integration

### Send Test Event from GHL

1. Create a test contact in GoHighLevel
2. Add to pipeline, move through stages
3. Check workflow execution log

### Verify in Triple Whale

1. Go to **SQL Editor** in Triple Whale
2. Query recent events:
```sql
SELECT * FROM custom_pixel_events_table
WHERE event_date = today()
ORDER BY event_timestamp DESC
LIMIT 10;
```

## Pipeline Stage Reference

| Stage Type | Event | Use Case |
|------------|-------|----------|
| Initial Contact | `lead` | Form submission, inbound call |
| Marketing Qualified | `mql` | Engaged with content, fits ICP |
| Sales Qualified | `sql` | Budget/authority/need confirmed |
| Demo/Meeting | `book_demo` | Meeting scheduled |
| Proposal | `opportunity` | Active deal |
| Closed Won | `custom` | Revenue event |

## Troubleshooting

### Events Not Appearing

```bash
# Test API key
curl https://api.triplewhale.com/api/v2/users/api-keys/me \
  -H "x-api-key: YOUR_KEY"
```

### Webhook Not Firing

1. Check GHL workflow is published and active
2. Verify trigger conditions match test contact
3. Review workflow execution history

### Attribution Not Linking

- Ensure email/phone matches between Pixel and API events
- Verify Pixel is installed: `TriplePixel('State')` returns "Ready"

## Environment Variables

```env
TRIPLE_WHALE_API_KEY=tw_xxxxxxxxxxxxx
GHL_WEBHOOK_SECRET=your_webhook_secret
```

## Next Steps

- [ ] Install Triple Pixel on lead capture pages
- [ ] Configure custom events for key interactions
- [ ] Build attribution dashboard in Triple Whale
- [ ] Set up alerts for pipeline velocity changes

See [Full Integration Guide](./TRIPLE_WHALE_API.md) for complete documentation.
