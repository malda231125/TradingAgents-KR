import json
from pathlib import Path
from unittest.mock import patch

from scripts.check_self_loop_triggers import run_daily_check
from tradingagents.self_loop.records import save_decision_record


def _record():
    return {
        "schema_version": "self-loop-decision-v1",
        "ticker": "000660",
        "analysis_date": "2026-06-24",
        "review_due": "2026-07-01",
        "decision": "buy_review",
        "thesis": "Bullish above support.",
        "key_risk_triggers": ["종가 100000 하회와 거래량 증가"],
        "prediction_checklist": ["000660 should remain above 100000"],
        "resolved": False,
    }


def _retro():
    return {
        "schema_version": "self-loop-retrospective-v1",
        "ticker": "000660",
        "analysis_date": "2026-06-24",
        "check_date": "2026-06-25",
        "review_due": "2026-07-01",
        "decision": "buy_review",
        "overall": "miss",
        "price_result": {"status": "available", "start_close": 105000, "end_close": 98000, "return_pct": -6.67},
        "checklist_results": [{"item": "000660 should remain above 100000", "status": "miss", "reason": "98000 close"}],
        "lesson": "Respect confirmed support breaks.",
    }


def test_daily_check_keeps_not_fired_record_pending(tmp_path):
    save_decision_record(_record(), base_dir=tmp_path)

    with patch("scripts.check_self_loop_triggers.run_retrospective", return_value=_retro()):
        with patch("scripts.check_self_loop_triggers.build_evidence_packet", return_value={"data_quality": {}}):
            with patch(
                "scripts.check_self_loop_triggers.detect_key_risk_trigger_with_subscription_ai",
                return_value={"status": "not_fired", "trigger_fired": False, "reasoning": "support held"},
            ):
                result = run_daily_check(base_dir=tmp_path, as_of_date="2026-06-25")

    assert result["checked"][0]["status"] == "pending"
    assert result["checked"][0]["trigger_status"] == "not_fired"
    saved = json.loads((Path(tmp_path) / "decisions" / "2026-06-24" / "000660.json").read_text())
    assert saved["resolved"] is False


def test_daily_check_reviews_immediately_when_trigger_fires(tmp_path):
    save_decision_record(_record(), base_dir=tmp_path)

    with patch("scripts.check_self_loop_triggers.run_retrospective", return_value=_retro()):
        with patch("scripts.check_self_loop_triggers.build_evidence_packet", return_value={"data_quality": {}}):
            with patch(
                "scripts.check_self_loop_triggers.detect_key_risk_trigger_with_subscription_ai",
                return_value={
                    "status": "fired",
                    "trigger_fired": True,
                    "matched_triggers": ["종가 100000 하회와 거래량 증가"],
                    "reasoning": "98000 close broke support",
                },
            ):
                with patch("scripts.self_loop_review.run_retrospective", return_value=_retro()):
                    result = run_daily_check(base_dir=tmp_path, as_of_date="2026-06-25")

    assert result["checked"][0]["status"] == "reviewed"
    assert result["checked"][0]["reason"] == "trigger_fired"
    saved = json.loads((Path(tmp_path) / "decisions" / "2026-06-24" / "000660.json").read_text())
    assert saved["resolved"] is True
    assert saved["resolved_reason"] == "trigger_fired"
