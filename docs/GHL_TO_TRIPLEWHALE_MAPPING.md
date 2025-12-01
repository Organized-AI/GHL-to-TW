# GoHighLevel to TripleWhale
## Order Data Mapping & Transformation Guide

---

## Executive Summary

This document details the analysis process and field mapping required to transform GoHighLevel (GHL) webhook payloads into TripleWhale Orders API format. The integration enables real-time order attribution for Marisa Peer's RTT business, connecting CRM sales data with TripleWhale's analytics platform.

---

## Analysis Process

The mapping was determined through systematic analysis of both the source (GHL webhook) and target (TripleWhale API) data structures:

1. **Identified Target Schema:** Started with the TripleWhale Orders API required fields: customer object (id, email, phone, first_name, last_name), shop, order_id, platform, created_at, currency, and order_revenue.

2. **Analyzed Source Payload:** Examined the GHL webhook payload structure, identifying 200+ fields including contact information, custom fields, attribution data, and sales-specific fields.

3. **Matched Direct Fields:** Mapped fields with 1:1 correspondence (contact_id → customer.id, email → customer.email, etc.).

4. **Identified Transformations:** Determined fields requiring parsing or computation (revenue extraction from product string, date format conversion).

5. **Documented Attribution Bonus:** Noted additional attribution fields (fbclid, fbc, fbp, IP, User Agent) available for enhanced tracking.

---

## Field Mapping Reference

### Direct Mappings

These fields transfer directly from GHL to TripleWhale with no transformation required:

| TripleWhale Field | GHL Source Field | Example Value |
|-------------------|------------------|---------------|
| `customer.id` | `contact_id` | `51OXKpJQro4XpNLpWDEv` |
| `customer.email` | `email` | `rochavale@verizon.net` |
| `customer.phone` | `phone` | `+17322775150` |
| `customer.first_name` | `first_name` | `Jackie` |
| `customer.last_name` | `last_name` | `Vale` |

### Computed/Transformed Fields

These fields require transformation logic:

| TW Field | GHL Source | Transformation | Result |
|----------|------------|----------------|--------|
| `shop` | Hardcoded | Static value | `rtt.com` |
| `order_id` | `contact_id` + date | Concatenate | `{contact_id}_{date}` |
| `platform` | Hardcoded | Static value | `ghl` |
| `created_at` | `Sales Reporting - Purchase Date` | ISO 8601 conversion | `2025-11-28T00:00:00.000Z` |
| `currency` | Inferred from $ symbol | Default USD | `USD` |
| `order_revenue` | `Product Sale on Call` | Regex extraction + sum | `9750` |

---

## Transformation Logic Details

### Revenue Extraction

The most complex transformation is extracting order revenue from the `Product Sale on Call` field.

**Example input:**
```
"AE RTT Accelerator VC Deposit ($950) + Balance ($8800.00)"
```

**Transformation steps:**

1. Apply regex pattern to extract all currency values: `/\$([0-9,]+(?:\.[0-9]{2})?)/g`
2. Remove commas from extracted values
3. Parse as float and sum all matches
4. **Result:** $950 + $8,800 = **9750**

**JavaScript implementation:**
```javascript
function extractRevenue(productString) {
  const regex = /\$([0-9,]+(?:\.[0-9]{2})?)/g;
  let total = 0;
  let match;
  while ((match = regex.exec(productString)) !== null) {
    total += parseFloat(match[1].replace(/,/g, ''));
  }
  return total;
}
```

### Order ID Generation

GHL does not provide a native order/transaction ID in the webhook. Three options were considered:

| Option | Method | Pros | Cons |
|--------|--------|------|------|
| 1 | `{contact_id}_{purchase_date}` | Simple, debuggable | Not unique if multiple purchases same day |
| 2 | Use `IFSSignedTag` field | Native ID | Not always populated |
| 3 | Hash of contact + product + date | Guaranteed unique | Not human-readable |

**Recommended approach:** Option 1 for simplicity and debuggability.

### Date Conversion

The `Sales Reporting - Purchase Date` field contains a date string (e.g., `2025-11-28`) that must be converted to ISO 8601 format with timezone.

```javascript
function convertToISO(dateString) {
  // Input: "2025-11-28"
  // Output: "2025-11-28T00:00:00.000Z"
  return `${dateString}T00:00:00.000Z`;
}
```

Since GHL doesn't provide time information, we append `T00:00:00.000Z` for midnight UTC.

---

## Bonus: Attribution Data

The GHL webhook contains rich attribution data in the `contact.attributionSource` object that can enhance Meta CAPI tracking:

| Field | Value |
|-------|-------|
| `fbclid` | `PAZXh0bgNhZW0BMABhZGlkAasr...` (truncated) |
| `fbc` | `fb.1.1764031930752.PAZXh0bgNhZW0...` (truncated) |
| `fbp` | `fb.1.1764031930754.405282270393668254` |
| `ip` | `72.76.128.52` |
| `userAgent` | `Mozilla/5.0 (iPhone; CPU iPhone OS 18_6_2...)` |
| `utmSource` | `fb` |
| `utmCampaign` | `MYOSIN_CM_INTEGRATED_2025-11-8` |

> **Important:** This attribution data (fbclid, IP, User Agent) directly addresses the 67% → 75% CAPI coverage gap identified in the Challenges By Marisa audit. Routing this data to Meta CAPI alongside TripleWhale could significantly improve attribution accuracy.

---

## Final Transformed Output

The complete transformation produces this TripleWhale-compatible JSON:

```json
{
  "customer": {
    "id": "51OXKpJQro4XpNLpWDEv",
    "email": "rochavale@verizon.net",
    "phone": "+17322775150",
    "first_name": "Jackie",
    "last_name": "Vale"
  },
  "shop": "rtt.com",
  "order_id": "51OXKpJQro4XpNLpWDEv_2025-11-28",
  "platform": "ghl",
  "created_at": "2025-11-28T00:00:00.000Z",
  "currency": "USD",
  "order_revenue": 9750
}
```

---

## GHL Webhook Field Reference

### Key Fields Used

| Category | Field Path | Purpose |
|----------|------------|---------|
| **Contact** | `contact_id` | Unique customer identifier |
| **Contact** | `email` | Customer email |
| **Contact** | `phone` | Customer phone (E.164 format) |
| **Contact** | `first_name` | Customer first name |
| **Contact** | `last_name` | Customer last name |
| **Custom** | `Product Sale on Call` | Product name with pricing |
| **Custom** | `Sales Reporting - Purchase Date` | Transaction date |
| **Custom** | `IFSSignedTag` | Alternative order ID |
| **Attribution** | `contact.attributionSource.fbclid` | Facebook Click ID |
| **Attribution** | `contact.attributionSource.fbc` | Facebook Cookie |
| **Attribution** | `contact.attributionSource.fbp` | Facebook Browser ID |
| **Attribution** | `contact.attributionSource.ip` | Client IP address |
| **Attribution** | `contact.attributionSource.userAgent` | Browser user agent |
| **Location** | `location.id` | GHL Location ID: `2atK5dRxfG7jh7sp7Yjo` |

---

## API Reference

### TripleWhale Orders API

**Endpoint:** `https://api.triplewhale.com/api/v2/data-in/orders`

**Method:** `POST`

**Headers:**
```
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

---

*Document generated for Marisa Peer / RTT GHL-TripleWhale Integration Project*
