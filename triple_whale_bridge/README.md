# Triple Whale Bridge

GoHighLevel to Triple Whale webhook integration service for full-funnel marketing attribution.

## Overview

Triple Whale Bridge receives webhooks from GoHighLevel CRM and transforms them into Triple Whale attribution events. This enables you to:

- Track offline conversions (leads, MQLs, SQLs, opportunities) in Triple Whale
- See which ad campaigns produce qualified leads and closed deals
- Calculate true ROAS across the entire customer lifecycle
- Build custom attribution dashboards with CRM data

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   GoHighLevel    │     │  Triple Whale    │     │   Triple Whale   │
│      CRM         │────▶│     Bridge       │────▶│    Attribution   │
│                  │     │                  │     │                  │
│ Pipeline Changes │     │ Transform &      │     │ Full Customer    │
│ Contact Events   │     │ Send Events      │     │ Journey Data     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

## Quick Start

### 1. Get Your Triple Whale API Key

1. Go to **Triple Whale Dashboard > Settings > API Keys**
2. Click **Generate an API Key**
3. Enable scope: **Orders: Write**
4. Copy the key (shown only once)

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your TRIPLE_WHALE_API_KEY
```

### 3. Run with Docker

```bash
docker-compose up -d
```

Or run locally:

```bash
pip install -r requirements.txt
python -m triple_whale_bridge --port 8000
```

### 4. Configure GoHighLevel Webhook

1. Create a workflow with trigger: **Pipeline Stage Changed**
2. Add action: **Webhook (Outbound)**
3. Set URL: `https://your-domain.com/webhook/ghl`
4. Method: POST
5. (Optional) Add `X-Webhook-Secret` header for security

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/ghl` | POST | Main webhook receiver for all GHL events |
| `/webhook/ghl/opportunity` | POST | Dedicated endpoint for pipeline changes |
| `/webhook/ghl/contact` | POST | Dedicated endpoint for contact events |
| `/health` | GET | Health check |
| `/config` | GET | View current pipeline mappings |
| `/config/reload` | POST | Reload configuration without restart |
| `/test/transform` | POST | Test transformation without sending |

## Pipeline Stage Mappings

Configure how GHL pipeline stages map to Triple Whale events in `config/pipeline_mappings.yaml`:

```yaml
pipelines:
  "Main Sales Pipeline":
    stages:
      "New Lead":
        event_type: "lead"
        value_multiplier: 0.0

      "Qualified":
        event_type: "mql"
        value_multiplier: 0.10

      "Demo Scheduled":
        event_type: "book_demo"
        value_multiplier: 0.25

      "Proposal Sent":
        event_type: "opportunity"
        value_multiplier: 0.50

      "Closed Won":
        event_type: "custom"
        custom_event_name: "closed_won"
        value_multiplier: 1.0
        include_revenue: true
```

### Event Types

| Type | Use Case |
|------|----------|
| `lead` | Initial lead capture |
| `mql` | Marketing Qualified Lead |
| `sql` | Sales Qualified Lead |
| `book_demo` | Demo/meeting scheduled |
| `opportunity` | Active deal/proposal |
| `custom` | Any custom conversion |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TRIPLE_WHALE_API_KEY` | Yes | Triple Whale API key |
| `WEBHOOK_SECRET` | No | Secret for `X-Webhook-Secret` validation |
| `GHL_WEBHOOK_SECRET` | No | Secret for GHL signature validation |
| `PIPELINE_CONFIG_PATH` | No | Custom config file path |
| `LOG_LEVEL` | No | DEBUG, INFO, WARNING, ERROR |
| `PORT` | No | Server port (default: 8000) |

## Testing

### Test Transformation

```bash
curl -X POST http://localhost:8000/test/transform \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "pipelineName": "Main Sales Pipeline",
    "pipelineStage": "Qualified",
    "leadValue": 10000
  }'
```

### Run Unit Tests

```bash
pytest triple_whale_bridge/tests/ -v
```

## Architecture

```
triple_whale_bridge/
├── __main__.py          # CLI entry point
├── core/
│   ├── server.py        # FastAPI application
│   ├── schema.py        # Pydantic models
│   ├── api.py           # Triple Whale client
│   ├── transformers.py  # GHL → TW transformation
│   ├── auth.py          # Webhook authentication
│   └── utils.py         # Utilities
├── config/
│   └── pipeline_mappings.yaml  # Stage mappings
└── tests/               # Test suite
```

## Deployment Options

### Docker (Recommended)

```bash
docker-compose up -d
```

### Cloud Functions

Deploy `core/server.py` as:
- AWS Lambda with API Gateway
- Google Cloud Functions
- Vercel Serverless Functions
- Cloudflare Workers

### VPS/Server

```bash
# With systemd
sudo systemctl enable triple-whale-bridge
sudo systemctl start triple-whale-bridge

# With PM2
pm2 start "python -m triple_whale_bridge" --name triple-whale-bridge
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "triple_whale_configured": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Logs

Logs are written to:
- stdout (console)
- `~/.config/triple-whale-bridge/logs/bridge.log` (Linux)
- `~/Library/Application Support/triple-whale-bridge/logs/bridge.log` (macOS)

## Troubleshooting

### Events Not Appearing in Triple Whale

1. Check API key is valid: `GET /health` shows `triple_whale_configured: true`
2. Verify email/phone is included in webhook payload
3. Check stage is mapped: `GET /config`
4. Test transformation: `POST /test/transform`

### Webhook Not Receiving Data

1. Verify GHL workflow is published and active
2. Check trigger conditions match
3. Review GHL workflow execution history
4. Test with: `curl -X POST http://localhost:8000/webhook/ghl -d '{...}'`

### Rate Limiting

Triple Whale limits: 1,000 events/min. The client includes automatic retry with exponential backoff for rate limit errors.

## Related Documentation

- [Triple Whale API Guide](../docs/triple_whale/TRIPLE_WHALE_API.md)
- [GoHighLevel Integration Quick Start](../docs/triple_whale/GHL_INTEGRATION_QUICKSTART.md)
- [Triple Whale Official Docs](https://triplewhale.readme.io/reference/data-in-api-use-cases)
- [GoHighLevel Webhooks](https://help.gohighlevel.com/support/solutions/articles/155000003299-actions-webhook)

## License

Apache 2.0 - See [LICENSE](../LICENSE)
