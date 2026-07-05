"""Tests for the CLI LLM client and factory routing.

Verifies:
1. CLIChatModel subprocess invocation and response wrapping
2. CLIClient configuration and model validation
3. Factory routing for "claude-cli" provider
4. Message conversion to prompt string
5. Error handling (timeout, missing CLI, empty output, retries)
6. AIMessage compatibility (content, tool_calls=[])
"""

import unittest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from cli.stats_handler import StatsCallbackHandler
from tradingagents.llm_clients.cli_client import (
    CLIChatModel,
    CLIClient,
    _messages_to_prompt,
    CLI_BACKEND_SPECS,
    MODEL_MAPS,
)
from tradingagents.llm_clients.factory import create_llm_client


class TestMessagesToPrompt(unittest.TestCase):
    """Test _messages_to_prompt conversion."""

    def test_string_input(self):
        result = _messages_to_prompt("hello")
        self.assertEqual(result, "hello")

    def test_langchain_messages(self):
        messages = [
            SystemMessage(content="You are helpful."),
            HumanMessage(content="What is 2+2?"),
        ]
        result = _messages_to_prompt(messages)
        self.assertIn("[System Instructions]", result)
        self.assertIn("You are helpful.", result)
        self.assertIn("What is 2+2?", result)

    def test_dict_messages(self):
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Hello"},
        ]
        result = _messages_to_prompt(messages)
        self.assertIn("[System Instructions]", result)
        self.assertIn("Be concise.", result)
        self.assertIn("Hello", result)

    def test_ai_message_included(self):
        messages = [
            HumanMessage(content="Hi"),
            AIMessage(content="Hello!"),
            HumanMessage(content="Follow up"),
        ]
        result = _messages_to_prompt(messages)
        self.assertIn("[Previous Assistant Response]", result)
        self.assertIn("Hello!", result)

    def test_empty_list(self):
        result = _messages_to_prompt([])
        self.assertEqual(result, "")

    def test_tuple_messages(self):
        messages = [
            ("system", "System tuple"),
            ("human", "Hello from tuple"),
            ("assistant", "Previous tuple response"),
        ]
        result = _messages_to_prompt(messages)
        self.assertIn("[System Instructions]", result)
        self.assertIn("System tuple", result)
        self.assertIn("Hello from tuple", result)
        self.assertIn("[Previous Assistant Response]", result)


class TestCLIChatModel(unittest.TestCase):
    """Test CLIChatModel behavior."""

    def test_llm_type(self):
        model = CLIChatModel(cli_backend="claude", cli_command="claude")
        self.assertEqual(model._llm_type, "cli-claude")

    def test_identifying_params(self):
        model = CLIChatModel(
            cli_backend="claude",
            cli_command="claude",
            cli_model="opus",
            cli_timeout=120,
        )
        params = model._identifying_params
        self.assertEqual(params["cli_backend"], "claude")
        self.assertEqual(params["cli_command"], "claude")
        self.assertEqual(params["cli_model"], "opus")
        self.assertEqual(params["cli_timeout"], 120)

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Analysis complete.",
            stderr="",
        )

        model = CLIChatModel(cli_command="claude", cli_model="sonnet")
        result = model._call_cli("test prompt")

        self.assertEqual(result, "Analysis complete.")
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], "claude")
        self.assertIn("-p", cmd)
        # The prompt is now sent via stdin, NOT as a command-line argument,
        # so it must not appear anywhere in the argv list.
        self.assertNotIn("test prompt", cmd)
        self.assertEqual(call_args.kwargs.get("input"), "test prompt")

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_claude_effort_arg(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Analysis complete.",
            stderr="",
        )

        llm = CLIClient(model="opus-4.8", cli_backend="claude", effort="max").get_llm()
        result = llm._call_cli("test prompt")

        self.assertEqual(result, "Analysis complete.")
        cmd = mock_run.call_args[0][0]
        self.assertIn("--effort", cmd)
        self.assertIn("max", cmd)
        self.assertIn("claude-opus-4-8", cmd)

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_codex_reads_output_file(self, mock_run):
        def side_effect(cmd, **kwargs):
            output_path = cmd[cmd.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("Codex final response.")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        model = CLIChatModel(
            cli_backend="codex",
            cli_command="codex",
            cli_subcommand=("exec",),
            cli_model="gpt-5.4",
            cli_prompt_flag=None,
            cli_model_flag="--model",
            cli_output_format_flag=None,
            cli_output_format=None,
            cli_prompt_stdin_sentinel="-",
            cli_output_file_flag="--output-last-message",
            cli_output_mode="output_file",
            cli_extra_args=("--color", "never"),
        )
        result = model._call_cli("test prompt")

        self.assertEqual(result, "Codex final response.")
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], "codex")
        self.assertIn("exec", cmd)
        self.assertIn("--output-last-message", cmd)
        self.assertEqual(cmd[-1], "-")
        self.assertEqual(call_args.kwargs.get("input"), "test prompt")

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_returns_aimessage(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Report here.",
            stderr="",
        )

        model = CLIChatModel(cli_command="claude", cli_model="sonnet")
        messages = [HumanMessage(content="Analyze this")]
        result = model.invoke(messages)

        self.assertIsInstance(result, AIMessage)
        self.assertEqual(result.content, "Report here.")
        self.assertEqual(result.tool_calls, [])

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_nonzero_exit_retries(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error occurred",
        )

        model = CLIChatModel(cli_command="claude", cli_model="sonnet", cli_max_retries=2)

        with self.assertRaises(RuntimeError) as ctx:
            model._call_cli("test")

        self.assertIn("error occurred", str(ctx.exception))
        self.assertEqual(mock_run.call_count, 2)

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=10)

        model = CLIChatModel(cli_command="claude", cli_timeout=10, cli_max_retries=1)

        with self.assertRaises(TimeoutError):
            model._call_cli("test")

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_command_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()

        model = CLIChatModel(cli_command="nonexistent_cli")

        with self.assertRaises(FileNotFoundError) as ctx:
            model._call_cli("test")

        self.assertIn("nonexistent_cli", str(ctx.exception))

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_call_cli_empty_output_retries(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        model = CLIChatModel(cli_command="claude", cli_max_retries=2)

        with self.assertRaises(RuntimeError) as ctx:
            model._call_cli("test")

        self.assertIn("empty output", str(ctx.exception))
        self.assertEqual(mock_run.call_count, 2)

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_invoke_with_string_input(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="String response.",
            stderr="",
        )

        model = CLIChatModel(cli_command="claude")
        result = model.invoke("Hello there")

        self.assertIsInstance(result, AIMessage)
        self.assertEqual(result.content, "String response.")

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_invoke_with_dict_messages(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Dict response.",
            stderr="",
        )

        model = CLIChatModel(cli_command="claude")
        result = model.invoke([
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Hi"},
        ])

        self.assertIsInstance(result, AIMessage)
        self.assertEqual(result.content, "Dict response.")

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_invoke_with_tuple_messages(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Tuple response.",
            stderr="",
        )

        model = CLIChatModel(cli_command="claude")
        result = model.invoke([
            ("system", "Use the tuple path."),
            ("human", "Analyze this tuple input."),
        ])

        self.assertIsInstance(result, AIMessage)
        self.assertEqual(result.content, "Tuple response.")
        # The prompt is delivered via stdin (`input=`), not as an argv slot.
        prompt = mock_run.call_args.kwargs["input"]
        self.assertIn("[System Instructions]", prompt)
        self.assertIn("Use the tuple path.", prompt)
        self.assertIn("Analyze this tuple input.", prompt)


class TestCLIClient(unittest.TestCase):
    """Test CLIClient wrapper."""

    def test_get_llm_returns_cli_chat_model(self):
        client = CLIClient(model="sonnet", cli_backend="claude")
        llm = client.get_llm()
        self.assertIsInstance(llm, CLIChatModel)
        self.assertEqual(llm.cli_command, "claude")
        self.assertEqual(llm.cli_model, "sonnet")

    def test_get_llm_with_opus(self):
        client = CLIClient(model="opus", cli_backend="claude")
        llm = client.get_llm()
        self.assertEqual(llm.cli_model, "opus")

    def test_get_llm_with_mapped_model(self):
        client = CLIClient(model="claude-haiku", cli_backend="claude")
        llm = client.get_llm()
        self.assertEqual(llm.cli_model, "haiku")

    def test_get_llm_codex_backend(self):
        client = CLIClient(model="gpt-5.4", cli_backend="codex")
        llm = client.get_llm()
        self.assertIsInstance(llm, CLIChatModel)
        self.assertEqual(llm.cli_command, "codex")
        self.assertEqual(llm.cli_subcommand, ("exec",))
        self.assertEqual(llm.cli_model, "gpt-5.4")
        self.assertEqual(llm.cli_output_mode, "output_file")

    def test_validate_model_known(self):
        client = CLIClient(model="sonnet", cli_backend="claude")
        self.assertTrue(client.validate_model())

    def test_validate_model_unknown(self):
        client = CLIClient(model="unknown-model-xyz", cli_backend="claude")
        self.assertFalse(client.validate_model())

    def test_validate_model_codex_known(self):
        client = CLIClient(model="gpt-5.4", cli_backend="codex")
        self.assertTrue(client.validate_model())

    def test_validate_model_codex_unknown(self):
        client = CLIClient(model="unknown-model-xyz", cli_backend="codex")
        self.assertFalse(client.validate_model())

    def test_custom_timeout_and_retries(self):
        client = CLIClient(model="sonnet", cli_backend="claude", timeout=600, max_retries=5)
        llm = client.get_llm()
        self.assertEqual(llm.cli_timeout, 600)
        self.assertEqual(llm.cli_max_retries, 5)

    def test_callbacks_passed_through(self):
        handler = StatsCallbackHandler()
        client = CLIClient(model="sonnet", cli_backend="claude", callbacks=[handler])
        llm = client.get_llm()
        self.assertEqual(llm.callbacks, [handler])

    @patch("tradingagents.llm_clients.cli_client.subprocess.run")
    def test_callbacks_receive_llm_events(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Callback response.",
            stderr="",
        )

        handler = StatsCallbackHandler()
        client = CLIClient(model="sonnet", cli_backend="claude", callbacks=[handler])
        llm = client.get_llm()
        llm.invoke("Track this call")

        self.assertEqual(handler.get_stats()["llm_calls"], 1)


class TestFactoryRouting(unittest.TestCase):
    """Test that factory correctly routes to CLI client."""

    def test_claude_cli_returns_cli_client(self):
        client = create_llm_client(provider="claude-cli", model="sonnet")
        self.assertIsInstance(client, CLIClient)

    def test_codex_cli_returns_cli_client(self):
        client = create_llm_client(provider="codex-cli", model="gpt-5.4")
        self.assertIsInstance(client, CLIClient)

    def test_claude_cli_get_llm(self):
        client = create_llm_client(provider="claude-cli", model="opus")
        llm = client.get_llm()
        self.assertIsInstance(llm, CLIChatModel)
        self.assertEqual(llm.cli_model, "opus")

    def test_codex_cli_get_llm(self):
        client = create_llm_client(provider="codex-cli", model="gpt-5.4")
        llm = client.get_llm()
        self.assertIsInstance(llm, CLIChatModel)
        self.assertEqual(llm.cli_command, "codex")
        self.assertEqual(llm.cli_model, "gpt-5.4")

    def test_unsupported_provider_raises(self):
        with self.assertRaises(ValueError):
            create_llm_client(provider="unsupported-xyz", model="test")


class TestModelMap(unittest.TestCase):
    """Test model name mapping."""

    def test_claude_opus_maps(self):
        self.assertEqual(MODEL_MAPS["claude"]["claude-opus"], "opus")

    def test_claude_sonnet_maps(self):
        self.assertEqual(MODEL_MAPS["claude"]["claude-sonnet"], "sonnet")

    def test_shorthand_opus(self):
        self.assertEqual(MODEL_MAPS["claude"]["opus"], "opus")

    def test_explicit_opus_48(self):
        self.assertEqual(MODEL_MAPS["claude"]["opus-4.8"], "claude-opus-4-8")

    def test_shorthand_haiku(self):
        self.assertEqual(MODEL_MAPS["claude"]["haiku"], "haiku")

    def test_codex_gpt_54_maps(self):
        self.assertEqual(MODEL_MAPS["codex"]["gpt-5.4"], "gpt-5.4")


class TestCLIDefaults(unittest.TestCase):
    """Test CLI default configuration."""

    def test_claude_defaults_exist(self):
        self.assertIn("claude", CLI_BACKEND_SPECS)

    def test_claude_defaults_structure(self):
        defaults = CLI_BACKEND_SPECS["claude"]
        self.assertEqual(defaults["command"], "claude")
        self.assertEqual(defaults["prompt_flag"], "-p")
        self.assertIn("model_flag", defaults)
        self.assertIn("output_format", defaults)

    def test_codex_defaults_structure(self):
        defaults = CLI_BACKEND_SPECS["codex"]
        self.assertEqual(defaults["command"], "codex")
        self.assertEqual(defaults["subcommand"], ("exec",))
        self.assertEqual(defaults["output_mode"], "output_file")
        self.assertEqual(defaults["prompt_stdin_sentinel"], "-")


if __name__ == "__main__":
    unittest.main()
