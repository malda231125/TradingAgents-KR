#!/usr/bin/env python3
"""Live verification script for Phase 4-C-B (peer financial context).

Run from repo root:
    source .venv/bin/activate
    python scripts/verify_phase_4cb.py

What it verifies (against the LIVE DART API):

  1. The DART `fnlttMultiAcnt` endpoint returns parseable BS/IS line items
     for a known peer set (Samsung 005930 + SK Hynix 000660 in 반도체).

  2. `compute_metrics_from_accounts` produces sensible ROE / debt / margin
     numbers from the live data (sanity-check against published Samsung
     2025 annual figures).

  3. `build_peer_context` end-to-end for three different stocks resolves
     the right sector, fetches the right peer set, and produces a
     peer_context block with target_vs_peer ranks:

       - 005930 (삼성전자) → KRX 반도체 (vs SK하이닉스, 한미반도체, ...)
       - 105560 (KB금융)   → KRX 은행   (vs 신한, 하나, 우리, ...)
       - 035420 (NAVER)   → K200 정보기술 (vs 카카오, LG에너지솔루션, ...)

  4. `build_fundamentals_packet` end-to-end attaches the peer_context to
     the FundamentalsPacket. Sample dump for KB금융 so the user can
     eyeball the peer comparison.

  5. An unmapped ticker produces a packet with `peer_context: None`.

  6. The serialized packet stays under the size budget, including the
     domestic peer_context and optional SEC global_peer_context blocks.

This script makes ~5-8 LIVE DART API calls and a handful of KIS calls.
It does NOT call any LLM. It should complete in well under 60 seconds
if DART and KIS are healthy.

Output is human-readable. Exits 0 on success and 1 on any failure.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from tradingagents.dataflows.dart_api import get_dart_multi_company_financials
from tradingagents.dataflows.feature_packets.fundamentals import (
    build_fundamentals_packet,
)
from tradingagents.dataflows.feature_packets.peer_context import (
    _default_bsns_year,
    build_peer_context,
    compute_metrics_from_accounts,
)
from tradingagents.dataflows.sector_index import (
    get_peer_stocks_in_sector,
    get_sector_for_stock,
)


TRADE_DATE = os.environ.get("VERIFY_TRADE_DATE", "2026-04-10")

SAMSUNG_CORP = "00126380"
SK_HYNIX_CORP = "00164779"


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
# Step 1 — direct DART fnlttMultiAcnt call
# ----------------------------------------------------------------------


def verify_multi_acnt_endpoint() -> bool:
    _section(f"Step 1: DART fnlttMultiAcnt direct call (year={_default_bsns_year(TRADE_DATE)})")

    year = _default_bsns_year(TRADE_DATE)
    try:
        data = get_dart_multi_company_financials(
            [SAMSUNG_CORP, SK_HYNIX_CORP],
            bsns_year=year,
            reprt_code="11011",
        )
    except Exception as exc:
        _fail(f"get_dart_multi_company_financials raised: {exc}")
        traceback.print_exc()
        return False

    if not data:
        _fail("DART returned empty result")
        return False

    if SAMSUNG_CORP not in data:
        _fail(f"Samsung corp_code {SAMSUNG_CORP} missing from response")
        return False

    samsung = data[SAMSUNG_CORP]
    expected_accounts = ["매출액", "영업이익", "당기순이익", "자산총계", "부채총계", "자본총계"]
    missing = [a for a in expected_accounts if a not in samsung and not any(a in k for k in samsung)]
    if missing:
        _fail(f"Samsung accounts missing: {missing}")
        return False

    _ok(f"Samsung response: {len(samsung)} unique accounts")
    _ok(f"SK Hynix response: {len(data.get(SK_HYNIX_CORP, {}))} unique accounts")
    return True


# ----------------------------------------------------------------------
# Step 2 — compute_metrics_from_accounts sanity check on live data
# ----------------------------------------------------------------------


def verify_metric_computation() -> bool:
    _section("Step 2: compute_metrics_from_accounts on live Samsung data")

    year = _default_bsns_year(TRADE_DATE)
    data = get_dart_multi_company_financials(
        [SAMSUNG_CORP], bsns_year=year, reprt_code="11011"
    )
    if not data or SAMSUNG_CORP not in data:
        _fail("could not fetch Samsung data")
        return False

    metrics = compute_metrics_from_accounts(data[SAMSUNG_CORP])
    _info(f"Samsung {year} metrics:")
    for k, v in metrics.items():
        _info(f"    {k}: {v}")

    if metrics["roe_pct"] is None or metrics["roe_pct"] < 5 or metrics["roe_pct"] > 25:
        _fail(f"ROE {metrics['roe_pct']} outside sanity band [5, 25]")
        return False
    if metrics["debt_ratio_pct"] is None or metrics["debt_ratio_pct"] < 10 or metrics["debt_ratio_pct"] > 80:
        _fail(f"Debt ratio {metrics['debt_ratio_pct']} outside sanity band [10, 80]")
        return False
    if metrics["operating_margin_pct"] is None or metrics["operating_margin_pct"] < 5:
        _fail(f"Operating margin {metrics['operating_margin_pct']} too low")
        return False

    _ok("Samsung metrics within sanity bands")
    return True


# ----------------------------------------------------------------------
# Step 3 — build_peer_context end-to-end for 3 sectors
# ----------------------------------------------------------------------


def verify_peer_context_build() -> bool:
    _section("Step 3: build_peer_context for mapped stocks")

    cases = [
        ("005930", "삼성전자", "KRX 반도체"),
        ("105560", "KB금융", "KRX 은행"),
        ("035420", "NAVER", "K200 정보기술"),
    ]

    all_ok = True
    for stock_code, name, expected_sector in cases:
        sector = get_sector_for_stock(stock_code)
        if sector != expected_sector:
            _fail(f"{stock_code} ({name}): expected sector {expected_sector}, got {sector}")
            all_ok = False
            continue

        peers = get_peer_stocks_in_sector(expected_sector, exclude=stock_code)
        _info(f"{stock_code} ({name}): {len(peers)} sector peers in mapping")

        try:
            ctx = build_peer_context(stock_code, TRADE_DATE)
        except Exception as exc:
            _fail(f"{stock_code}: build_peer_context raised: {exc}")
            traceback.print_exc()
            all_ok = False
            continue

        if ctx is None:
            _fail(
                f"{stock_code}: peer_context is None — check that DART corp_codes "
                "for sector peers are resolvable. Run: python -c "
                "'from tradingagents.dataflows.korea_ticker import get_corp_code; "
                "print(get_corp_code(\"...\"))' for the missing peers."
            )
            all_ok = False
            continue

        _ok(
            f"{stock_code} ({name}): peer_context built — "
            f"sector={ctx['sector']}, peer_count={ctx['peer_count']}"
        )
        roe = ctx["target_vs_peer"]["roe"]
        debt = ctx["target_vs_peer"]["debt_ratio"]
        _info(
            f"     ROE {roe.get('value_pct')}% rank={roe.get('rank')} "
            f"diff={roe.get('diff_vs_peer_median_pp')}pp"
        )
        _info(
            f"     debt {debt.get('value_pct')}% rank={debt.get('rank')} "
            f"diff={debt.get('diff_vs_peer_median_pp')}pp"
        )
        _info(f"     interpretation: {ctx.get('interpretation')}")

    return all_ok


# ----------------------------------------------------------------------
# Step 4 — full build_fundamentals_packet end-to-end
# ----------------------------------------------------------------------


def verify_fundamentals_packet_e2e() -> bool:
    _section("Step 4: build_fundamentals_packet end-to-end (KB금융)")

    try:
        packet = build_fundamentals_packet("105560", TRADE_DATE)
    except Exception as exc:
        _fail(f"build_fundamentals_packet raised: {exc}")
        traceback.print_exc()
        return False

    if packet.peer_context is None:
        _fail("KB금융 packet has peer_context=None — peer fetch failed")
        return False

    _ok(f"KB금융 packet built: peer_context attached, {len(packet.signals)} signals")
    _info(f"     packet size: {len(packet.to_prompt_block())} chars")
    _info(f"     evidence_refs: {len(packet.evidence_refs)}")
    for ref in packet.evidence_refs:
        _info(f"       · {ref}")
    _info(f"     signal bullets:")
    for s in packet.signals:
        _info(f"       · {s}")
    return True


# ----------------------------------------------------------------------
# Step 5 — unmapped stock omits peer_context
# ----------------------------------------------------------------------


def verify_unmapped_stock_omits_peer_context() -> bool:
    _section("Step 5: unmapped stock → peer_context omitted")

    unmapped_ticker = os.environ.get("VERIFY_UNMAPPED_TICKER", "950140")

    try:
        packet = build_fundamentals_packet(unmapped_ticker, TRADE_DATE)
    except Exception as exc:
        _fail(f"build_fundamentals_packet raised for {unmapped_ticker}: {exc}")
        return False

    if packet.peer_context is not None:
        _fail(f"{unmapped_ticker}: peer_context should be None, got {packet.peer_context}")
        return False

    if not any("peer_context 없음" in note for note in packet.data_quality_notes):
        _fail(
            f"{unmapped_ticker}: data_quality_notes does not include peer_context warning"
        )
        return False

    _ok(f"{unmapped_ticker}: peer_context omitted, warning recorded in data_quality_notes")
    return True


# ----------------------------------------------------------------------
# Step 6 — packet size budget
# ----------------------------------------------------------------------


def verify_packet_size_budget() -> bool:
    _section("Step 6: packet size budget check")

    try:
        packet = build_fundamentals_packet("105560", TRADE_DATE)
    except Exception as exc:
        _fail(f"build_fundamentals_packet raised: {exc}")
        return False

    block = packet.to_prompt_block()
    size = len(block)
    SOFT_MAX = 6500  # domestic peer_context + optional SEC global_peer_context
    if size > SOFT_MAX:
        _fail(f"packet size {size} chars exceeds soft max {SOFT_MAX}")
        return False
    _ok(f"KB금융 packet size: {size} chars (under {SOFT_MAX})")
    return True


# ----------------------------------------------------------------------
# Sample dump
# ----------------------------------------------------------------------


def dump_sample_packet() -> None:
    _section("Sample packet dump (105560 / KB금융)")
    try:
        packet = build_fundamentals_packet("105560", TRADE_DATE)
    except Exception as exc:
        print(f"  [FAIL] could not build sample packet: {exc}")
        return
    print(packet.to_prompt_block())


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------


def main() -> int:
    print(f"Phase 4-C-B live verification — trade_date={TRADE_DATE}")

    results = {}
    results["Step 1: multi_acnt endpoint"] = verify_multi_acnt_endpoint()
    results["Step 2: metric computation"] = verify_metric_computation()
    results["Step 3: peer_context build"] = verify_peer_context_build()
    results["Step 4: fundamentals e2e"] = verify_fundamentals_packet_e2e()
    results["Step 5: unmapped stock"] = verify_unmapped_stock_omits_peer_context()
    results["Step 6: packet size"] = verify_packet_size_budget()

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
        print("\n  → Phase 4-C-B live verification PASSED")
        return 0

    print("\n  → Phase 4-C-B live verification FAILED — see above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
