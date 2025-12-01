# Revenue Extraction Plan

## Current State

The CSV transformation tool (`csv-to-triplewhale/transform_csv.py`) currently:
- Sends orders to Triple Whale with `order_revenue: 0`
- Identifies customers via tags (`_customer`, `agreement signed`, etc.)
- Successfully processed 10,100 orders to Triple Whale

## Revenue Sources

### 1. CSV Tags (Partial Coverage)

The Tags field in the CSV export contains payment plan information for some contacts:

**Examples found in tags:**
- `deposit ($488.00) + payment plan (14 x $488.00)` → $7,320
- `12 pay deposit ($2950) + 12 pay ($615x12)` → $10,330
- `vc deposit (£X) + payment plan (N x £Y)` → GBP amounts
- `70. product purchase: foundation in hypnotherapy $49` → $49

**Current implementation** (`extract_order_revenue_from_tags` function):
- Parses deposit + payment plan patterns
- Handles USD ($) and GBP (£) amounts
- Returns `None` if no pattern found (defaults to 0)

**Limitation:** Not all customers have payment info in tags.

---

### 2. GHL API (Full Coverage)

The GHL API provides comprehensive payment data:

**Endpoints:**
- `GET /payments/transactions` - List all transactions
- `GET /payments/transactions?contactId={id}` - Transactions for specific contact
- `GET /opportunities/search?contactId={id}` - Deal values

**GHL MCP Server Configuration:**
```json
{
  "command": "npx",
  "args": [
    "-y", "mcp-remote",
    "https://services.leadconnectorhq.com/mcp/",
    "--header", "Authorization: Bearer {GHL_API_KEY}",
    "--header", "locationId: 2atK5dRxfG7jh7sp7Yjo"
  ]
}
```

**Available MCP Tools:**
- `payments_get-order-by-id` - Fetch order details
- `payments_list-transactions` - Paginated transaction list
- `contacts_get-contact` - Full contact details with custom fields

---

## Implementation Plan

### Phase 1: Enhanced Tag Parsing (Quick Win)

Improve `extract_order_revenue_from_tags()` to catch more patterns:

```python
# Additional patterns to add:
- "product purchase: {product} ${amount}"
- "full pay ${amount}"
- "{N} pay (${amount}x{N})"
- GBP patterns with £ symbol
```

**Effort:** 1-2 hours
**Coverage:** ~40% of customers with tag-based pricing

---

### Phase 2: GHL API Enrichment Script

Create `ghl_enrichment.py` to:
1. Read contact IDs from CSV
2. Query GHL API for transactions per contact
3. Sum successful transaction amounts
4. Output enriched CSV or update Triple Whale directly

```python
def get_contact_revenue(contact_id: str) -> float:
    """
    Query GHL API for all transactions for a contact.
    Sum amounts where status = 'succeeded' or 'paid'.
    """
    transactions = ghl_api.list_transactions(contactId=contact_id)
    return sum(t['amount'] for t in transactions if t['status'] in ['succeeded', 'paid'])
```

**Effort:** 4-6 hours
**Coverage:** 100% of customers with GHL payment records

---

### Phase 3: Triple Whale Update API

Use Triple Whale's update endpoint to enrich existing orders:

**Endpoint:** `PATCH /api/v2/data-in/orders/{order_id}`

```python
def update_order_revenue(order_id: str, revenue: float):
    requests.patch(
        f"https://api.triplewhale.com/api/v2/data-in/orders/{order_id}",
        json={"order_revenue": revenue},
        headers={"x-api-key": TW_API_KEY}
    )
```

This allows updating the 10,100 orders already sent with `order_revenue: 0`.

---

## Recommended Approach

1. **Immediate:** Run enhanced tag parsing on remaining 8,468 contacts
2. **Next:** Build GHL API enrichment script for contacts missing tag revenue
3. **Then:** Update existing Triple Whale orders via PATCH endpoint

---

## GHL API Authentication

**Location ID:** `2atK5dRxfG7jh7sp7Yjo`

**API Base:** `https://services.leadconnectorhq.com`

**Required Headers:**
```
Authorization: Bearer {GHL_API_KEY}
Content-Type: application/json
Version: 2021-07-28
```

Store credentials in `.env`:
```
GHL_API_KEY=your_api_key_here
GHL_LOCATION_ID=2atK5dRxfG7jh7sp7Yjo
```
