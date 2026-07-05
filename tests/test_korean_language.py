"""Tests for Phase 5-5 Korean language report output.

Verifies:
1. get_language_instruction returns Korean instruction when config is "ko"
2. get_language_instruction returns an explicit English instruction when config
   is "en" (the input context is Korean-heavy, so English must be stated too)
3. Default config has report_language set to "ko"
4. All agent files import get_language_instruction
"""

import unittest
from unittest.mock import patch

from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.default_config import DEFAULT_CONFIG


class TestGetLanguageInstruction(unittest.TestCase):
    """Test the language instruction helper."""

    def test_korean_returns_instruction(self):
        result = get_language_instruction({"report_language": "ko"})
        self.assertIn("한국어", result)
        self.assertIn("Korean", result)

    def test_english_returns_instruction(self):
        # English is emitted explicitly too: the input context (KIS data, Korean
        # company names, Naver news) is Korean-heavy, so without a "respond in
        # English" the model would follow the data and answer in Korean.
        result = get_language_instruction({"report_language": "en"})
        self.assertIn("English", result)

    def test_missing_key_falls_back_to_english(self):
        result = get_language_instruction({})
        self.assertIn("English", result)

    def test_none_config_uses_global(self):
        # Should not crash when config is None (falls back to get_config)
        result = get_language_instruction(None)
        self.assertIsInstance(result, str)


class TestDefaultConfigLanguage(unittest.TestCase):
    """Test that default config has Korean language set."""

    def test_default_is_korean(self):
        self.assertEqual(DEFAULT_CONFIG["report_language"], "ko")


class TestAgentImports(unittest.TestCase):
    """Test that all agent modules import get_language_instruction."""

    def test_market_analyst_imports(self):
        import tradingagents.agents.analysts.market_analyst as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_news_analyst_imports(self):
        import tradingagents.agents.analysts.news_analyst as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_fundamentals_analyst_imports(self):
        import tradingagents.agents.analysts.fundamentals_analyst as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_social_analyst_imports(self):
        import tradingagents.agents.analysts.social_media_analyst as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_bull_researcher_imports(self):
        import tradingagents.agents.researchers.bull_researcher as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_bear_researcher_imports(self):
        import tradingagents.agents.researchers.bear_researcher as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_aggressive_debator_imports(self):
        import tradingagents.agents.risk_mgmt.aggressive_debator as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_conservative_debator_imports(self):
        import tradingagents.agents.risk_mgmt.conservative_debator as m
        self.assertTrue(hasattr(m, "get_language_instruction"))

    def test_neutral_debator_imports(self):
        import tradingagents.agents.risk_mgmt.neutral_debator as m
        self.assertTrue(hasattr(m, "get_language_instruction"))


if __name__ == "__main__":
    unittest.main()
