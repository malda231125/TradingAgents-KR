#!/usr/bin/env python3
"""Live verification script for Phase 4-C-A (sector index → MarketPacket).

Run this from the repo root after Phase 4-C-A is committed:

    source .venv/bin/activate
    python scripts/verify_phase_4ca.py

What it verifies (against the LIVE KIS API):

  1. The KIS `inquire-daily-indexchartprice` endpoint actually returns data
     for the sector codes we hardcoded (4003 KRX 반도체, 4005 KRX 은행,
     2013 K200 정보기술). If any of these fail, the mapping or the endpoint
     specification is wrong.

  2. `build_market_packet()` end-to-end for three different stocks that
     resolve to three different sectors:
       - 005930 (삼성전자) → KRX 반도체
       - 105560 (KB금융)   → KRX 은행
       - 035420 (NAVER)   → K200 정보기술
     Each one should produce a packet with a populated `sector_context`
     block whose `sector_name` matches the expected sector.

  3. `build_market_packet()` for an unmapped ticker should produce a packet
     where `sector_context is None` (graceful no-fallback behavior).

  4. The packet's serialized JSON size is within the target band
     (~1k–3k chars), confirming the context-shrink goal.

This script makes ~6–8 LIVE KIS API calls. It does NOT call any LLM and
does NOT run the full TradingAgentsGraph. It should complete in under
30 seconds if KIS is healthy.

Output is printed in human-readable form. The script exits 0 on success
and 1 on any verification failure.
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime

# Make sure imports work when run from repo root
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env so that KIS_APP_KEY/KIS_APP_SECRET/etc. are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from tradingagents.dataflows.feature_packets.market import build_market_packet
from tradingagents.dataflows.kis_vendor import get_kis_sector_index_dataframe
from tradingagents.dataflows.sector_index import (
    KIS_SECTOR_INDEX_CODES,
    get_sector_index_code_for_stock,
)


# Configurable trade date — change this to a recent business day if 2026-04-10
# isn't available in your KIS account.
TRADE_DATE = os.environ.get("VERIFY_TRADE_DATE", "2026-04-10")
LOOKBACK_START = os.environ.get("VERIFY_START_DATE", "2026-01-10")


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(f" {title}")
    print("=" * 72)


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _info(msg: str) -> None:
    print(f"  · {msg}")


# ----------------------------------------------------------------------
# Step 1 — direct sector index endpoint check
# ----------------------------------------------------------------------


def verify_sector_index_endpoint() -> bool:
    _section(f"Step 1: Direct KIS sector index endpoint (TRADE_DATE={TRADE_DATE})")
    sectors_to_check = [
        ("KRX 반도체", "4003"),
        ("KRX 은행", "4005"),
        ("K200 정보기술", "2013"),
    ]

    all_ok = True
    for name, code in sectors_to_check:
        # Sanity-check the static mapping first
        if KIS_SECTOR_INDEX_CODES.get(name) != code:
            _fail(f"sector_index.py mapping mismatch: {name} → {KIS_SECTOR_INDEX_CODES.get(name)}, expected {code}")
            all_ok = False
            continue

        try:
            df = get_kis_sector_index_dataframe(code, LOOKBACK_START, TRADE_DATE)
        except Exception as exc:
            _fail(f"{name} ({code}): KIS request raised: {exc}")
            traceback.print_exc()
            all_ok = False
            continue

        if df is None or df.empty:
            _fail(f"{name} ({code}): KIS returned empty DataFrame")
            all_ok = False
            continue

        if "Close" not in df.columns or df["Close"].isna().all():
            _fail(f"{name} ({code}): no Close column or all NaN")
            all_ok = False
            continue

        first_date = df.iloc[0]["Date"]
        last_date = df.iloc[-1]["Date"]
        last_close = df.iloc[-1]["Close"]
        _ok(
            f"{name} ({code}): {len(df)} rows, "
            f"{first_date} → {last_date}, latest close {last_close}"
        )

    return all_ok


# ----------------------------------------------------------------------
# Step 2 — full build_market_packet for mapped stocks
# ----------------------------------------------------------------------


def verify_build_market_packet_for_mapped_stocks() -> bool:
    _section("Step 2: build_market_packet for mapped stocks")

    expected_cases = [
        ("005930", "삼성전자", "KRX 반도체"),
        ("105560", "KB금융", "KRX 은행"),
        ("035420", "NAVER", "K200 정보기술"),
    ]

    all_ok = True
    for ticker, name, expected_sector in expected_cases:
        # First, sanity-check the static lookup
        lookup = get_sector_index_code_for_stock(ticker)
        if lookup is None:
            _fail(f"{ticker} ({name}): not in STOCK_TO_SECTOR — check sector_index.py")
            all_ok = False
            continue
        actual_sector_name, actual_code = lookup
        if actual_sector_name != expected_sector:
            _fail(
                f"{ticker} ({name}): expected sector '{expected_sector}', "
                f"got '{actual_sector_name}'"
            )
            all_ok = False
            continue

        try:
            packet = build_market_packet(ticker, TRADE_DATE)
        except Exception as exc:
            _fail(f"{ticker} ({name}): build_market_packet raised: {exc}")
            traceback.print_exc()
            all_ok = False
            continue

        if packet.sector_context is None:
            _fail(
                f"{ticker} ({name}): sector_context is None — "
                "either KIS sector call failed or sector data was too short"
            )
            all_ok = False
            continue

        if packet.sector_context.get("sector_name") != expected_sector:
            _fail(
                f"{ticker} ({name}): packet sector_name mismatch — "
                f"expected '{expected_sector}', got "
                f"'{packet.sector_context.get('sector_name')}'"
            )
            all_ok = False
            continue

        # Sanity-check the structure of sector_context
        required_fields = [
            "sector_name",
            "sector_change_5d_pct",
            "stock_relative_5d_pct",
            "outperforming_sector_short_term",
        ]
        missing = [f for f in required_fields if f not in packet.sector_context]
        if missing:
            _fail(f"{ticker}: sector_context missing fields: {missing}")
            all_ok = False
            continue

        # Sector signal bullets should mention the sector
        sector_signal_bullets = [s for s in packet.signals if expected_sector in s]

        prompt_size = len(packet.to_prompt_block())
        _ok(
            f"{ticker} ({name}): sector_context populated → "
            f"{packet.sector_context.get('sector_name')} "
            f"5d={packet.sector_context.get('sector_change_5d_pct')} "
            f"rel={packet.sector_context.get('stock_relative_5d_pct')}"
        )
        _info(f"     packet size: {prompt_size} chars")
        _info(f"     sector signal bullets: {len(sector_signal_bullets)}")
        if sector_signal_bullets:
            _info(f"     sample: {sector_signal_bullets[0]}")
        _info(f"     evidence_refs: {len(packet.evidence_refs)}")
        for ref in packet.evidence_refs:
            _info(f"       · {ref}")

    return all_ok


# ----------------------------------------------------------------------
# Step 3 — unmapped stock should get sector_context=None
# ----------------------------------------------------------------------


def verify_unmapped_stock_omits_sector_context() -> bool:
    _section("Step 3: unmapped stock → sector_context omitted")

    # Use a small/obscure ticker that should NOT be in STOCK_TO_SECTOR.
    # Override via env if needed.
    unmapped_ticker = os.environ.get("VERIFY_UNMAPPED_TICKER", "950140")

    lookup = get_sector_index_code_for_stock(unmapped_ticker)
    if lookup is not None:
        _fail(
            f"{unmapped_ticker}: unexpectedly IS in STOCK_TO_SECTOR → "
            f"{lookup}. Pick a different VERIFY_UNMAPPED_TICKER and re-run."
        )
        return False
    _ok(f"{unmapped_ticker}: confirmed not in STOCK_TO_SECTOR")

    try:
        packet = build_market_packet(unmapped_ticker, TRADE_DATE)
    except Exception as exc:
        _fail(f"{unmapped_ticker}: build_market_packet raised: {exc}")
        traceback.print_exc()
        return False

    if packet.sector_context is not None:
        _fail(
            f"{unmapped_ticker}: sector_context should be None, got "
            f"{packet.sector_context}"
        )
        return False

    _ok(f"{unmapped_ticker}: sector_context is None as expected")
    _info(f"     packet built with {len(packet.signals)} signal bullets and "
          f"regime={packet.regime.get('label')}")
    return True


# ----------------------------------------------------------------------
# Step 4 — packet size budget check
# ----------------------------------------------------------------------


def verify_packet_size_budget() -> bool:
    _section("Step 4: packet size budget check")

    try:
        packet = build_market_packet("005930", TRADE_DATE)
    except Exception as exc:
        _fail(f"build_market_packet failed: {exc}")
        return False

    block = packet.to_prompt_block()
    size = len(block)

    SOFT_MAX = 4000  # current target ceiling
    if size > SOFT_MAX:
        _fail(
            f"packet size {size} chars exceeds soft max {SOFT_MAX} — "
            "this regresses the context-shrink goal"
        )
        return False

    _ok(f"삼성전자 packet size: {size} chars (under {SOFT_MAX})")
    return True


# ----------------------------------------------------------------------
# Optional: dump the full packet for one stock so the user can eyeball it
# ----------------------------------------------------------------------


def dump_sample_packet() -> None:
    _section("Sample packet dump (005930 / 삼성전자)")
    try:
        packet = build_market_packet("005930", TRADE_DATE)
    except Exception as exc:
        print(f"  [FAIL] could not build sample packet: {exc}")
        return

    print(packet.to_prompt_block())


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------


def main() -> int:
    print(f"Phase 4-C-A live verification — trade_date={TRADE_DATE}")

    results = {}
    results["Step 1: sector endpoint"] = verify_sector_index_endpoint()
    results["Step 2: mapped stocks"] = verify_build_market_packet_for_mapped_stocks()
    results["Step 3: unmapped stock"] = verify_unmapped_stock_omits_sector_context()
    results["Step 4: packet size"] = verify_packet_size_budget()

    dump_sample_packet()

    _section("Summary")
    all_ok = True
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        marker = "  ✓" if ok else "  ✗"
        print(f"{marker} {status:5s} {name}")
        if not ok:
            all_ok = False

    if all_ok:
        print("\n  → Phase 4-C-A live verification PASSED")
        return 0

    print("\n  → Phase 4-C-A live verification FAILED — see above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
