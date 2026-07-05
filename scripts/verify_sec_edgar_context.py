#!/usr/bin/env python3
"""Live verification for SEC EDGAR global peer context."""

from __future__ import annotations

import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(".env")

from tradingagents.dataflows.feature_packets.global_peer import build_global_peer_context


def main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "005930"
    trade_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")

    if not os.environ.get("SEC_USER_AGENT"):
        print("FAIL: SEC_USER_AGENT is not configured")
        return 1

    try:
        ctx = build_global_peer_context(ticker, trade_date)
    except Exception as exc:
        print(f"FAIL: SEC context build raised: {exc}")
        return 1

    if not ctx:
        print(f"FAIL: SEC global peer context is empty for {ticker}")
        return 1

    filings = ctx.get("recent_filings") or []
    snapshots = ctx.get("peer_fundamental_snapshot") or []
    print(f"PASS: SEC global peer context built for {ticker} / {trade_date}")
    print(f"  sector: {ctx.get('sector')}")
    print(f"  peers: {', '.join(ctx.get('peer_universe') or [])}")
    print(f"  recent filings: {len(filings)}")
    print(f"  peer snapshots: {len(snapshots)}")
    print(f"  interpretation: {ctx.get('interpretation')}")

    if not filings and not snapshots:
        print("FAIL: no filings or snapshots were generated")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
