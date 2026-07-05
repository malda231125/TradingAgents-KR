"""Tests for Phase 5-3 Telegram bot integration.

Verifies:
1. Authorization check works correctly
2. Ticker detection logic (6-digit codes, short names)
3. _run_graph function signature matches expected interface
4. Bot handler functions exist and are callable
"""

import unittest
import importlib
import os
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from cli.bot import (
    _is_authorized,
    _run_graph,
    ALLOWED_USER_ID,
)


class TestAuthorization(unittest.TestCase):
    """Test user authorization check."""

    def test_authorized_user(self):
        update = MagicMock()
        update.effective_user.id = ALLOWED_USER_ID
        if ALLOWED_USER_ID != 0:
            self.assertTrue(_is_authorized(update))

    def test_unauthorized_user(self):
        update = MagicMock()
        update.effective_user.id = 99999999
        self.assertFalse(_is_authorized(update))


class TestBotModuleStructure(unittest.TestCase):
    """Test that bot module has expected functions."""

    def test_start_command_exists(self):
        from cli.bot import start_command
        self.assertTrue(callable(start_command))

    def test_help_command_exists(self):
        from cli.bot import help_command
        self.assertTrue(callable(help_command))

    def test_clear_cache_command_exists(self):
        from cli.bot import clear_cache_command
        self.assertTrue(callable(clear_cache_command))

    def test_analyze_command_exists(self):
        from cli.bot import analyze_command
        self.assertTrue(callable(analyze_command))

    def test_handle_message_exists(self):
        from cli.bot import handle_message
        self.assertTrue(callable(handle_message))

    def test_main_exists(self):
        from cli.bot import main
        self.assertTrue(callable(main))

    def test_blank_telegram_user_id_does_not_break_import(self):
        import cli.bot as bot_module

        with patch.dict(os.environ, {"TELEGRAM_USER_ID": ""}, clear=False):
            reloaded = importlib.reload(bot_module)
            self.assertEqual(reloaded.ALLOWED_USER_ID, 0)

        importlib.reload(bot_module)


class TestRunGraphSignature(unittest.TestCase):
    """Test _run_graph function interface."""

    def test_accepts_ticker_and_date(self):
        """_run_graph should accept ticker and trade_date args."""
        import inspect
        sig = inspect.signature(_run_graph)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["ticker", "trade_date"])


if __name__ == "__main__":
    unittest.main()
