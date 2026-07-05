import unittest
from unittest.mock import MagicMock, patch

from cli.utils import (
    select_deep_thinking_agent,
    select_llm_provider,
    select_shallow_thinking_agent,
)


class TestCliWorkflow(unittest.TestCase):

    @patch("cli.utils.questionary.select")
    def test_select_llm_provider_returns_claude_cli(self, mock_select):
        prompt = MagicMock()
        prompt.ask.return_value = "claude-cli"
        mock_select.return_value = prompt

        provider, backend_url = select_llm_provider()

        self.assertEqual(provider, "claude-cli")
        self.assertIsNone(backend_url)

    @patch("cli.utils.questionary.select")
    def test_select_llm_provider_returns_codex_cli(self, mock_select):
        prompt = MagicMock()
        prompt.ask.return_value = "codex-cli"
        mock_select.return_value = prompt

        provider, backend_url = select_llm_provider()

        self.assertEqual(provider, "codex-cli")
        self.assertIsNone(backend_url)

    @patch("cli.utils.questionary.select")
    def test_select_shallow_agent_supports_claude_cli(self, mock_select):
        prompt = MagicMock()
        prompt.ask.return_value = "sonnet"
        mock_select.return_value = prompt

        selected = select_shallow_thinking_agent("claude-cli")

        self.assertEqual(selected, "sonnet")

    @patch("cli.utils.questionary.select")
    def test_select_deep_agent_supports_claude_cli(self, mock_select):
        prompt = MagicMock()
        prompt.ask.return_value = "opus"
        mock_select.return_value = prompt

        selected = select_deep_thinking_agent("claude-cli")

        self.assertEqual(selected, "opus")

    @patch("cli.utils.questionary.select")
    def test_select_shallow_agent_supports_codex_cli(self, mock_select):
        prompt = MagicMock()
        prompt.ask.return_value = "gpt-5.4"
        mock_select.return_value = prompt

        selected = select_shallow_thinking_agent("codex-cli")

        self.assertEqual(selected, "gpt-5.4")

    @patch("cli.utils.questionary.select")
    def test_select_deep_agent_supports_codex_cli(self, mock_select):
        prompt = MagicMock()
        prompt.ask.return_value = "gpt-5.4"
        mock_select.return_value = prompt

        selected = select_deep_thinking_agent("codex-cli")

        self.assertEqual(selected, "gpt-5.4")

    def test_select_shallow_agent_rejects_non_cli_provider(self):
        with self.assertRaises(ValueError):
            select_shallow_thinking_agent("openai")

    def test_select_deep_agent_rejects_non_cli_provider(self):
        with self.assertRaises(ValueError):
            select_deep_thinking_agent("anthropic")


if __name__ == "__main__":
    unittest.main()
