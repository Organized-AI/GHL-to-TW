# GHL to Triple Whale

Transform GoHighLevel CRM contact data into Triple Whale order format for attribution tracking.

## Quick Start

```bash
cd csv-to-triplewhale
pip install -r requirements.txt
cp .env.example .env  # Add your API key

# Dry run (preview without sending)
python transform_csv.py --csv /path/to/contacts.csv --dry-run

# Send to Triple Whale
python transform_csv.py --csv /path/to/contacts.csv

# Process specific range
python transform_csv.py --csv /path/to/contacts.csv --start 0 --limit 100
```

## Project Structure

```
├── csv-to-triplewhale/
│   ├── transform_csv.py    # Main transformation script
│   ├── requirements.txt    # Python dependencies
│   ├── .env.example        # Environment template
│   └── .gitignore
├── docs/
│   ├── GHL_TO_TRIPLEWHALE_MAPPING.md   # Field mapping reference
│   └── REVENUE_EXTRACTION_PLAN.md      # Plan for order revenue enrichment
├── mcp/
│   └── prod-ghl-mcp.json   # GHL MCP server configuration
├── .claude/skills/
│   └── triple-whale-bridge/SKILL.md    # Claude skill for transformations
└── README.md
```

## Configuration

Set in `.env`:
```
TW_API_KEY=your_triple_whale_api_key
TW_SHOP_DOMAIN=rtt.com
DEFAULT_CURRENCY=GBP
DEFAULT_ORDER_REVENUE=0
```

## Documentation

- [Field Mapping Guide](docs/GHL_TO_TRIPLEWHALE_MAPPING.md) - How GHL fields map to Triple Whale
- [Revenue Extraction Plan](docs/REVENUE_EXTRACTION_PLAN.md) - Plan for extracting order revenue from tags and GHL API

## GHL MCP Server

The `mcp/prod-ghl-mcp.json` contains configuration for connecting to GoHighLevel via MCP:

```bash
# Add to Claude Desktop config (~/Library/Application Support/Claude/claude_desktop_config.json)
# Or Claude Code config (~/.claude.json)
```

Available tools: `contacts_get-contact`, `payments_list-transactions`, `opportunities_search`

## How It Works

1. Reads GHL contact CSV export
2. Filters for customers (via `_customer`, `agreement signed` tags)
3. Transforms to Triple Whale order format
4. Sends to `/data-in/orders` endpoint

## Status

- ✅ 10,100 orders sent to Triple Whale
- ⏳ 8,468 orders remaining
- 📋 Revenue enrichment planned via GHL API
