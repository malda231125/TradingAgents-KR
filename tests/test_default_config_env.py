import importlib
import os
import unittest
from unittest.mock import patch

import tradingagents.default_config as default_config


class TestDefaultConfigEnv(unittest.TestCase):
    def tearDown(self):
        importlib.reload(default_config)

    def test_codex_provider_model_defaults(self):
        defaults = default_config.get_cli_model_defaults("codex-cli")
        self.assertEqual(defaults["quick"], "gpt-5.5")
        self.assertEqual(defaults["deep"], "gpt-5.5")

    def test_env_overrides_apply_on_reload(self):
        with patch.dict(
            os.environ,
            {
                "TRADINGAGENTS_LLM_PROVIDER": "codex-cli",
                "TRADINGAGENTS_QUICK_MODEL": "gpt-5.5",
                "TRADINGAGENTS_DEEP_MODEL": "gpt-5.5",
                "TRADINGAGENTS_CLI_TIMEOUT": "900",
                "TRADINGAGENTS_CLI_MAX_RETRIES": "4",
                "TRADINGAGENTS_CLI_EFFORT": "max",
            },
            clear=False,
        ):
            module = importlib.reload(default_config)
            self.assertEqual(module.DEFAULT_CONFIG["llm_provider"], "codex-cli")
            self.assertEqual(module.DEFAULT_CONFIG["quick_think_llm"], "gpt-5.5")
            self.assertEqual(module.DEFAULT_CONFIG["deep_think_llm"], "gpt-5.5")
            self.assertEqual(module.DEFAULT_CONFIG["cli_timeout"], 900)
            self.assertEqual(module.DEFAULT_CONFIG["cli_max_retries"], 4)
            self.assertEqual(module.DEFAULT_CONFIG["cli_effort"], "max")

    def test_explicit_provider_is_honored_over_detection(self):
        # An explicit provider must win even if another CLI is installed.
        with patch.object(default_config.shutil, "which", return_value="/usr/bin/codex"):
            self.assertEqual(
                default_config.resolve_default_provider("claude-cli"), "claude-cli"
            )

    def test_blank_provider_prefers_codex_when_both_installed(self):
        with patch.object(default_config.shutil, "which", return_value="/usr/bin/x"):
            self.assertEqual(default_config.resolve_default_provider(""), "codex-cli")
            self.assertEqual(default_config.resolve_default_provider(None), "codex-cli")

    def test_blank_provider_picks_claude_when_only_claude_installed(self):
        def only_claude(cmd):
            return "/usr/bin/claude" if cmd == "claude" else None

        with patch.object(default_config.shutil, "which", side_effect=only_claude):
            self.assertEqual(default_config.detect_cli_provider(), "claude-cli")
            self.assertEqual(default_config.resolve_default_provider(None), "claude-cli")

    def test_blank_provider_falls_back_to_codex_when_no_cli(self):
        with patch.object(default_config.shutil, "which", return_value=None):
            self.assertIsNone(default_config.detect_cli_provider())
            self.assertEqual(default_config.resolve_default_provider(None), "codex-cli")
