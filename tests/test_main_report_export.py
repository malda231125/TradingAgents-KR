from pathlib import Path

from main import _build_export_state, _write_markdown_report
from scripts.export_run_to_md import render_markdown


def test_build_export_state_adapts_graph_state():
    final_state = {
        "market_report": "market",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "investment_plan": "investment",
        "trader_investment_plan": "trader",
        "final_trade_decision": "decision",
        "investment_debate_state": {
            "history": "debate history",
            "judge_decision": "judge",
        },
        "risk_debate_state": {
            "history": "risk history",
        },
    }

    state = _build_export_state(final_state, "005930", "2026-04-30", "BUY", 12.5)

    assert state["ticker"] == "005930"
    assert state["trade_date"] == "2026-04-30"
    assert state["signal"] == "BUY"
    assert state["wall_clock_seconds"] == 12.5
    assert state["market_report"] == "market"
    assert state["news_report"] == "news"
    assert state["fundamentals_report"] == "fundamentals"
    assert state["investment_plan"] == "investment"
    assert state["trader_investment_plan"] == "trader"
    assert state["final_trade_decision"] == "decision"
    assert state["debate_state"]["history"] == "debate history"
    assert state["debate_state"]["judge_decision"] == "judge"
    assert state["risk_state"]["history"] == "risk history"


def test_write_markdown_report_saves_under_results(tmp_path):
    config = {"results_dir": str(tmp_path / "results")}

    complete_path, timestamped_path = _write_markdown_report(
        config,
        "005930",
        "2026-04-30",
        "# Samsung report\n",
    )

    expected_dir = Path(config["results_dir"]) / "005930" / "2026-04-30"
    assert complete_path == expected_dir / "complete_report.md"
    assert timestamped_path.parent == expected_dir
    assert timestamped_path.name.startswith("005930_2026-04-30_")
    assert timestamped_path.suffix == ".md"
    assert complete_path.read_text(encoding="utf-8") == "# Samsung report\n"
    assert timestamped_path.read_text(encoding="utf-8") == "# Samsung report\n"


def test_render_markdown_omits_duplicate_research_manager_decision():
    markdown = render_markdown(
        {
            "ticker": "005930",
            "trade_date": "2026-04-30",
            "investment_plan": "same research manager text",
            "debate_state": {"judge_decision": "same research manager text"},
        }
    )

    assert "## Research Manager decision" not in markdown
    assert markdown.count("same research manager text") == 1


def test_render_markdown_keeps_distinct_research_manager_decision():
    markdown = render_markdown(
        {
            "ticker": "005930",
            "trade_date": "2026-04-30",
            "report_language": "en",
            "investment_plan": "investment plan text",
            "debate_state": {"judge_decision": "distinct judge decision"},
        }
    )

    assert "## Research Manager decision" in markdown
    assert "distinct judge decision" in markdown
    assert "investment plan text" in markdown
