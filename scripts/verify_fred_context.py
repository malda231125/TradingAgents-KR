#!/usr/bin/env python3
"""Live verification for FRED-backed US macro context."""

from __future__ import annotations

import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(".env")

from tradingagents.dataflows.feature_packets.us_macro import build_us_macro_context


def main() -> int:
    trade_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    if not os.environ.get("FRED_API_KEY"):
        print("FAIL: FRED_API_KEY is not configured")
        return 1

    try:
        ctx = build_us_macro_context(trade_date)
    except Exception as exc:
        print(f"FAIL: FRED context build raised: {exc}")
        return 1

    if not ctx:
        print("FAIL: FRED context is empty")
        return 1

    available = 0
    for block in ("rates", "risk", "dollar", "macro"):
        for item in (ctx.get(block) or {}).values():
            if isinstance(item, dict) and item.get("latest") is not None:
                available += 1

    print(f"PASS: FRED context built for {trade_date}")
    print(f"  confidence: {ctx.get('confidence')}")
    print(f"  available latest fields: {available}")
    print(f"  interpretation: {ctx.get('interpretation')}")

    if available < 5:
        print("FAIL: fewer than 5 latest fields were available")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
