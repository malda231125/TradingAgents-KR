"""Tests for event-driven self-loop review."""

import datetime as dt

import pandas as pd

from scripts.self_loop_review import review_open_prediction, should_review
from tradingagents.self_loop.records import build_decision_record, save_decision_record


def _rec(**overrides):
    record = {"resolved": False, "review_due": "2026-07-01", "analysis_date": "2026-06-24"}
    record.update(overrides)
    return record


def test_should_review_false_when_resolved():
    assert should_review(_rec(resolved=True), "2026-07-05", True) is False


def test_should_review_true_when_trigger_fires_early():
    assert should_review(_rec(), "2026-06-25", True) is True


def test_should_review_false_when_no_trigger_and_not_due():
    assert should_review(_rec(), "2026-06-25", False) is False


def test_should_review_true_at_review_due_timeout():
    assert should_review(_rec(), "2026-07-01", False) is True


def _fake_price(ticker, start, end):
    dates = pd.date_range("2026-06-20", "2026-06-27", freq="D")
    return pd.DataFrame({"date": dates, "close": [100, 101, 102, 103, 104, 105, 106, 107]})


def _seed(tmp_path):
    final_state = {
        "market_report": "market",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "final_trade_decision": "BUY",
    }
    record = build_decision_record(
        ticker="005930",
        analysis_date="2026-06-24",
        signal="BUY",
        final_state=final_state,
        report_path="report.md",
        review_horizon_days=5,
        trading_day_fn=lambda _date, _days: dt.date(2026, 7, 1),
        use_ai_extraction=False,
    )
    assert record["resolved"] is False
    save_decision_record(record, base_dir=tmp_path)


def test_trigger_fired_reviews_resolves_and_is_idempotent(tmp_path):
    _seed(tmp_path)
    result = review_open_prediction(
        ticker="005930",
        as_of_date="2026-06-25",
        trigger_fired=True,
        base_dir=tmp_path,
        use_ai_review=False,
        price_fetcher=_fake_price,
    )
    assert result["status"] == "reviewed"
    assert result["reason"] == "trigger_fired"

    result2 = review_open_prediction(
        ticker="005930",
        as_of_date="2026-06-26",
        trigger_fired=True,
        base_dir=tmp_path,
        use_ai_review=False,
        price_fetcher=_fake_price,
    )
    assert result2["status"] == "already_resolved"


def test_pending_when_no_trigger_before_due(tmp_path):
    _seed(tmp_path)
    result = review_open_prediction(
        ticker="005930",
        as_of_date="2026-06-26",
        trigger_fired=False,
        base_dir=tmp_path,
        use_ai_review=False,
        price_fetcher=_fake_price,
    )
    assert result["status"] == "pending"


def test_none_when_no_record(tmp_path):
    result = review_open_prediction(
        ticker="000660",
        as_of_date="2026-06-26",
        trigger_fired=True,
        base_dir=tmp_path,
        use_ai_review=False,
        price_fetcher=_fake_price,
    )
    assert result["status"] == "none"
