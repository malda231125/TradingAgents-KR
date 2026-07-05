"""Integration test: cli/main.py run_analysis delegates to the self-loop.

These tests verify the *wiring* added when the self-improvement loop was
merged into the main workflow:

1. ``run_analysis`` calls ``run_self_loop`` (so every main run drives the loop).
2. The ``graph_runner`` it builds forwards the prior ``self_loop_context`` into
   ``create_initial_state`` (so retrospective lessons reach the fresh analysis).

The heavy interactive pieces (user prompts, the LLM graph, the Rich TUI) are
mocked so the test stays offline and deterministic.
"""

import os
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import cli.main as main


def _fake_selections():
    analyst = types.SimpleNamespace(value="market")
    return {
        "ticker": "005930",
        "analysis_date": "2026-06-23",
        "analysts": [analyst],
        "research_depth": 1,
        "shallow_thinker": "haiku",
        "deep_thinker": "sonnet",
        "backend_url": None,
        "llm_provider": "claude-cli",
    }


def _make_graph_mock():
    graph = MagicMock()
    # stream yields a single chunk that doubles as the final state
    graph.graph.stream.return_value = [
        {"messages": [], "final_trade_decision": "Hold with medium confidence."}
    ]
    graph.process_signal.return_value = "hold"
    graph.propagator.create_initial_state.return_value = {"messages": []}
    graph.propagator.get_graph_args.return_value = {}
    return graph


class _LiveStub:
    """Context-manager stand-in for rich.live.Live."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestCliSelfLoopIntegration(unittest.TestCase):
    def _run(self, fake_run_self_loop):
        graph = _make_graph_mock()
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                with patch.object(main, "get_user_selections", _fake_selections), \
                     patch.object(main, "TradingAgentsGraph", return_value=graph), \
                     patch.object(main, "Live", _LiveStub), \
                     patch.object(main, "create_layout", lambda: MagicMock()), \
                     patch.object(main, "update_display", lambda *a, **k: None), \
                     patch.object(main, "update_analyst_statuses", lambda *a, **k: None), \
                     patch.object(main, "update_research_team_status", lambda *a, **k: None), \
                     patch.object(main, "run_self_loop", side_effect=fake_run_self_loop), \
                     patch("typer.prompt", return_value="N"):
                    main.run_analysis()
            finally:
                os.chdir(cwd)
        return graph

    def test_run_analysis_delegates_to_run_self_loop(self):
        calls = {}

        def fake_run_self_loop(*, ticker, analysis_date, base_dir, graph_runner, use_ai_review):
            calls["ticker"] = ticker
            calls["analysis_date"] = analysis_date
            calls["use_ai_review"] = use_ai_review
            # invoke the runner exactly like the real orchestrator would
            final_state, decision = graph_runner(ticker, analysis_date, None)
            calls["decision"] = decision
            return {
                "retrospective_path": None,
                "decision_path": f"{base_dir}/decisions/x.json",
                "digest_path": f"{base_dir}/reports/x.md",
                "signal": decision,
            }

        self._run(fake_run_self_loop)

        self.assertEqual(calls["ticker"], "005930")
        self.assertEqual(calls["analysis_date"], "2026-06-23")
        self.assertTrue(calls["use_ai_review"])
        self.assertEqual(calls["decision"], "hold")

    def test_graph_runner_injects_self_loop_context(self):
        sentinel = "PRIOR-RETROSPECTIVE-AND-LESSONS"

        def fake_run_self_loop(*, ticker, analysis_date, base_dir, graph_runner, use_ai_review):
            graph_runner(ticker, analysis_date, sentinel)
            return {
                "retrospective_path": f"{base_dir}/r.md",
                "decision_path": f"{base_dir}/d.json",
                "digest_path": f"{base_dir}/g.md",
                "signal": "hold",
            }

        graph = self._run(fake_run_self_loop)

        # create_initial_state must receive the injected self_loop_context
        _, kwargs = graph.propagator.create_initial_state.call_args
        self.assertEqual(kwargs.get("self_loop_context"), sentinel)


if __name__ == "__main__":
    unittest.main()
