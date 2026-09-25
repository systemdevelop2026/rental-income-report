#!/usr/bin/env python3
"""Extract every figure from a Mana Mana monthly statement PDF.

Usage:
    python extract_statement.py <statement.pdf> [<statement.pdf> ...]

Prints one JSON object per statement.

Each statement is a 3-page PDF:
    page 1 - identity (building, month, statement no, billing period, owner)
    page 2 - "Statement Details": every figure, as a flat alternating
             label / value list
    page 3 - general information (ignored)

Page 2 is parsed by walking that alternating list, so new line items added by
Mana Mana are picked up automatically without changing this script.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

# A value line is a plain amount, an "RM x,xxx.xx" amount, or an "x/y" night count.
VALUE_RE = re.compile(r"^(?:RM\s?[\d,]+\.\d{2}|[\d,]+\.\d{2}|\d+/\d+)$")

IDENTITY = {
    "statement_month": r"Statement Month\s*\nTarikh Penyata\s*\n:\s*(.+)",
    "statement_no": r"Statement No\.\s*\nNo\. Penyata\s*\n:\s*(.+)",
    "billing_period": r"Billing Period\s*\nTempoh Billing\s*\n:\s*(.+)",
    "unit": r"Unit No\.\s*\nNo\. Unit\s*\n:\s*(.+)",
    "owners": r"Owner Name\s*\nNama Pemilik\s*\n:\s*(.+)",
    "beneficiary": r"Beneficiary Name\s*\nNama Akaun\s*\n:\s*(.+)",
    "bank_account": r"Bank Account\s*\nNo\. Akaun\s*\n:\s*(.+)",
}

# Headings on the details page - they carry no value of their own.
HEADINGS = {
    "Statement Details",
    "Revenue",
    "RM",
    "(-)Direct Expenses",
    "(-)Operation Expenses",
}

# Order matters for reporting; every one of these is an operating-expense line.
OPEX_KEYS = [
    "Electricity",
    "Water",
    "Internet",
    "STR Fees",
    "Sales & Marketing",
    "Repair & Maintenance",
    "Room Cleaning",
    "Laundry",
    "Account & Admin",
    "Room's Amenities",
    "Others",
]

# Only the charges that actually appear in a given month are deducted.
MO_KEYS = [
    "MO Maintenance Fee",
    "MO Sinking Fund",
    "MO Assessment Fee",
    "MO Quit Rent",
    "IWK Sewerage Charges",
    "MO Fire Insurance",
]

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def amount(text):
    """'RM 5,824.60' -> 5824.6. Returns None when the text is not an amount."""
    try:
        return float(text.replace("RM", "").replace(",", "").strip())
    except ValueError:
        return None


def clean_label(label):
    """Drop the trailing ':' and any '(-) ' prefix from a statement label."""
    lab = label.strip().rstrip(":").strip()
    return re.sub(r"^\(-\)\s*", "", lab)


def parse(path):
    """Return one dict of everything the statement contains."""
    doc = pymupdf.open(path)
    pages = [p.get_text() for p in doc]
    doc.close()
    full = "\n".join(pages)

    out = {"file": Path(path).name}
    for key, pattern in IDENTITY.items():
        m = re.search(pattern, full)
        out[key] = m.group(1).strip() if m else None

    detail = pages[1] if len(pages) > 1 else full
    items, pending = {}, None
    for line in (l.strip() for l in detail.splitlines()):
        if not line:
            continue
        if VALUE_RE.match(line):
            if pending:
                items[pending] = line
            pending = None
        elif line in HEADINGS:
            pending = None
        else:
            pending = line

    out["items"] = {clean_label(k): v for k, v in items.items()}
    out["figures"] = {k: amount(v) for k, v in out["items"].items() if amount(v) is not None}

    trip = out["items"].get("Hosted Trip")
    if trip and "/" in trip:
        hosted, available = (int(x) for x in trip.split("/"))
        out["hosted_nights"] = hosted
        out["available_nights"] = available
        out["occupancy_rate"] = round(hosted / available * 100, 2)

    rate = out["items"].get("Average room rate")
    if rate:
        out["avg_room_rate"] = amount(rate)

    return out


def main(argv):
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    for p in paths:
        print(json.dumps(parse(p), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
