#!/usr/bin/env python3
"""
CSV to Triple Whale Orders Transformer

Ingests a GHL contacts CSV export and sends order data to Triple Whale's
/data-in/orders endpoint.

Usage:
    # Dry run (preview only, no API calls)
    python transform_csv.py --csv /path/to/contacts.csv --dry-run

    # Send to Triple Whale
    python transform_csv.py --csv /path/to/contacts.csv

    # Process specific rows
    python transform_csv.py --csv /path/to/contacts.csv --limit 10
    python transform_csv.py --csv /path/to/contacts.csv --start 0 --limit 5
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TW_API_KEY = os.getenv("TW_API_KEY", "")
TW_SHOP_DOMAIN = os.getenv("TW_SHOP_DOMAIN", "rtt.com")
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "GBP")
DEFAULT_ORDER_REVENUE = float(os.getenv("DEFAULT_ORDER_REVENUE", "0"))

TW_ORDERS_ENDPOINT = "https://api.triplewhale.com/api/v2/data-in/orders"


def normalize_name(name: Optional[str]) -> str:
    """Normalize name to title case."""
    if not name:
        return ""
    return name.strip().title()


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone to E.164 format."""
    if not phone:
        return None

    cleaned = phone.strip()
    if cleaned.startswith("+"):
        return cleaned

    # Remove non-digits
    digits = re.sub(r"\D", "", cleaned)

    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    elif len(digits) > 10:
        return f"+{digits}"

    return None


def normalize_email(email: Optional[str]) -> Optional[str]:
    """Normalize email address."""
    if not email:
        return None
    normalized = email.strip().lower()
    if "@" in normalized and "." in normalized:
        return normalized
    return None


def parse_created_date(date_str: Optional[str]) -> str:
    """Parse date string to ISO 8601 format."""
    if not date_str:
        return datetime.utcnow().isoformat() + "Z"

    # Already in ISO format
    if "T" in date_str:
        return date_str

    return date_str


def extract_order_revenue_from_tags(tags: str) -> Optional[float]:
    """
    Extract order revenue from tags if possible.

    Looks for patterns like:
    - "deposit ($488.00) + payment plan (14 x $488.00)" -> 488 + (14*488) = 7320
    - "full pay gbp" -> use default
    - "12 pay deposit ($2950) + 12 pay ($615x12)" -> 2950 + (12*615) = 10330

    Returns None if no price pattern found, uses default in that case.
    """
    if not tags:
        return None

    tags_lower = tags.lower()

    # Pattern: deposit ($X) + payment plan (N x $Y)
    deposit_pattern = r"deposit\s*\(\$?([\d,]+(?:\.\d{2})?)\)\s*\+\s*payment\s*plan\s*\((\d+)\s*x\s*\$?([\d,]+(?:\.\d{2})?)\)"
    match = re.search(deposit_pattern, tags_lower)
    if match:
        deposit = float(match.group(1).replace(",", ""))
        count = int(match.group(2))
        payment = float(match.group(3).replace(",", ""))
        return deposit + (count * payment)

    # Pattern: N pay deposit ($X) + N pay ($YxN)
    alt_pattern = r"(\d+)\s*pay\s*deposit\s*\(\$?([\d,]+)\)\s*\+\s*\d+\s*pay\s*\(\$?([\d,]+)x(\d+)\)"
    match = re.search(alt_pattern, tags_lower)
    if match:
        deposit = float(match.group(2).replace(",", ""))
        payment = float(match.group(3).replace(",", ""))
        count = int(match.group(4))
        return deposit + (count * payment)

    # Pattern: vc deposit (£X) + payment plan (N x £Y)
    gbp_pattern = r"deposit\s*\(£([\d,]+(?:\.\d{2})?)\)\s*\+\s*payment\s*plan\s*\((\d+)\s*x\s*£([\d,]+(?:\.\d{2})?)\)"
    match = re.search(gbp_pattern, tags_lower)
    if match:
        deposit = float(match.group(1).replace(",", ""))
        count = int(match.group(2))
        payment = float(match.group(3).replace(",", ""))
        return deposit + (count * payment)

    return None


def is_customer(tags: str) -> bool:
    """Check if contact has customer tags indicating a purchase."""
    if not tags:
        return False

    customer_indicators = [
        "_customer",
        "agreement signed",
        "bought rtt",
        "product purchase",
    ]

    tags_lower = tags.lower()
    return any(indicator in tags_lower for indicator in customer_indicators)


def transform_row_to_order(row: Dict[str, str], row_index: int) -> Optional[Dict[str, Any]]:
    """Transform a CSV row to Triple Whale order format."""
    contact_id = row.get("Contact Id", "").strip()
    email = normalize_email(row.get("Email"))
    phone = normalize_phone(row.get("Phone"))
    first_name = normalize_name(row.get("First Name"))
    last_name = normalize_name(row.get("Last Name"))
    created_at = parse_created_date(row.get("Created"))
    tags = row.get("Tags", "")

    # Must have at least email or phone
    if not email and not phone:
        return None

    # Check if this is actually a customer
    if not is_customer(tags):
        return None

    # Try to extract revenue from tags, otherwise use default
    order_revenue = extract_order_revenue_from_tags(tags)
    if order_revenue is None:
        order_revenue = DEFAULT_ORDER_REVENUE

    # Generate unique order ID
    order_id = f"GHL-{contact_id}" if contact_id else f"GHL-ROW-{row_index}"

    # Build customer object
    customer: Dict[str, Any] = {}
    if contact_id:
        customer["id"] = contact_id
    if email:
        customer["email"] = email
    if phone:
        customer["phone"] = phone
    if first_name:
        customer["first_name"] = first_name
    if last_name:
        customer["last_name"] = last_name

    # Build order
    order = {
        "customer": customer,
        "shop": TW_SHOP_DOMAIN,
        "order_id": order_id,
        "created_at": created_at,
        "currency": DEFAULT_CURRENCY,
        "order_revenue": order_revenue,
    }

    return order


def send_order_to_triplewhale(order: Dict[str, Any]) -> Dict[str, Any]:
    """Send order to Triple Whale API."""
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": TW_API_KEY,
    }

    response = requests.post(TW_ORDERS_ENDPOINT, json=order, headers=headers)

    return {
        "status_code": response.status_code,
        "response": response.text,
        "success": response.status_code == 200,
    }


def process_csv(
    csv_path: str,
    dry_run: bool = True,
    start: int = 0,
    limit: Optional[int] = None,
    delay: float = 0.1,
) -> Dict[str, Any]:
    """
    Process CSV file and send orders to Triple Whale.

    Args:
        csv_path: Path to the CSV file
        dry_run: If True, only preview transformations without API calls
        start: Starting row index (0-based)
        limit: Maximum number of rows to process
        delay: Delay between API calls in seconds

    Returns:
        Summary of processing results
    """
    results = {
        "total_rows": 0,
        "customers_found": 0,
        "orders_created": 0,
        "orders_sent": 0,
        "errors": [],
        "skipped": 0,
    }

    orders: List[Dict[str, Any]] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            results["total_rows"] += 1

            # Skip rows before start
            if i < start:
                continue

            # Check limit
            if limit and (i - start) >= limit:
                break

            # Transform row
            order = transform_row_to_order(row, i)

            if order is None:
                results["skipped"] += 1
                continue

            results["customers_found"] += 1
            orders.append(order)

    # Process orders
    for order in orders:
        results["orders_created"] += 1

        if dry_run:
            print(f"\n[DRY RUN] Order #{results['orders_created']}:")
            print(json.dumps(order, indent=2))
        else:
            print(f"\nSending order {order['order_id']}...")
            result = send_order_to_triplewhale(order)

            if result["success"]:
                results["orders_sent"] += 1
                print(f"  Success: {result['response']}")
            else:
                error_msg = f"Order {order['order_id']}: {result['status_code']} - {result['response']}"
                results["errors"].append(error_msg)
                print(f"  Error: {error_msg}")

            # Rate limiting
            time.sleep(delay)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Transform GHL CSV contacts to Triple Whale orders"
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to the CSV file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview transformations without sending to API",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Starting row index (0-based)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of rows to process",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay between API calls in seconds",
    )

    args = parser.parse_args()

    # Validate API key if not dry run
    if not args.dry_run and not TW_API_KEY:
        print("Error: TW_API_KEY environment variable not set")
        print("Set it in .env file or export TW_API_KEY=your_key")
        sys.exit(1)

    # Check file exists
    if not os.path.exists(args.csv):
        print(f"Error: CSV file not found: {args.csv}")
        sys.exit(1)

    print(f"Processing CSV: {args.csv}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Shop: {TW_SHOP_DOMAIN}")
    print(f"Currency: {DEFAULT_CURRENCY}")
    print(f"Default Revenue: {DEFAULT_ORDER_REVENUE}")
    print("-" * 50)

    results = process_csv(
        csv_path=args.csv,
        dry_run=args.dry_run,
        start=args.start,
        limit=args.limit,
        delay=args.delay,
    )

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total rows scanned: {results['total_rows']}")
    print(f"Customers found: {results['customers_found']}")
    print(f"Orders created: {results['orders_created']}")
    print(f"Rows skipped (not customers): {results['skipped']}")

    if not args.dry_run:
        print(f"Orders sent successfully: {results['orders_sent']}")
        if results["errors"]:
            print(f"Errors: {len(results['errors'])}")
            for error in results["errors"]:
                print(f"  - {error}")


if __name__ == "__main__":
    main()
