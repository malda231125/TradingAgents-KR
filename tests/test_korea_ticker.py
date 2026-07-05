"""Tests for Korean ticker resolution module.

Verifies:
1. Built-in mapping contains major Korean stocks
2. resolve_ticker handles stock codes, corp_codes, names, partial names
3. get_corp_code and get_stock_code convenience functions
4. DART get_dart_events auto-resolves stock codes
5. Cache load/save operations
6. update_from_dart requires API key
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from tradingagents.dataflows.korea_ticker import (
    BUILTIN_TICKERS,
    get_instrument_profile,
    resolve_ticker,
    get_corp_code,
    get_stock_code,
    get_yfinance_candidates,
    update_from_dart,
    _load_cache,
    _save_cache,
)


class TestBuiltinTickers(unittest.TestCase):
    """Test the built-in fallback ticker mapping."""

    def test_samsung_electronics(self):
        self.assertIn("005930", BUILTIN_TICKERS)
        self.assertEqual(BUILTIN_TICKERS["005930"]["name"], "삼성전자")
        self.assertEqual(BUILTIN_TICKERS["005930"]["corp_code"], "00126380")

    def test_sk_hynix(self):
        self.assertIn("000660", BUILTIN_TICKERS)
        self.assertEqual(BUILTIN_TICKERS["000660"]["name"], "SK하이닉스")
        self.assertEqual(BUILTIN_TICKERS["000660"]["corp_code"], "00164779")

    def test_naver(self):
        self.assertIn("035420", BUILTIN_TICKERS)
        self.assertEqual(BUILTIN_TICKERS["035420"]["name"], "NAVER")
        self.assertEqual(BUILTIN_TICKERS["035420"]["corp_code"], "00266961")

    def test_major_stock_corp_codes_match_dart(self):
        """Guard against stale fallback corp_codes for high-traffic tickers."""
        expected = {
            "000660": "00164779",  # SK하이닉스
            "042700": "00161383",  # 한미반도체
            "240810": "01135941",  # 원익IPS
            "005380": "00164742",  # 현대자동차
            "000270": "00106641",  # 기아
            "035720": "00258801",  # 카카오
            "005490": "00155319",  # POSCO홀딩스
        }
        for stock_code, corp_code in expected.items():
            self.assertEqual(BUILTIN_TICKERS[stock_code]["corp_code"], corp_code)

    def test_builtin_corp_codes_are_unique(self):
        corp_codes = [info["corp_code"] for info in BUILTIN_TICKERS.values()]
        self.assertEqual(len(corp_codes), len(set(corp_codes)))

    def test_has_at_least_20_stocks(self):
        self.assertGreaterEqual(len(BUILTIN_TICKERS), 20)

    def test_all_entries_have_required_fields(self):
        for code, info in BUILTIN_TICKERS.items():
            self.assertIn("corp_code", info, f"Missing corp_code for {code}")
            self.assertIn("name", info, f"Missing name for {code}")
            self.assertTrue(len(code) == 6, f"Stock code should be 6 digits: {code}")
            self.assertTrue(len(info["corp_code"]) == 8, f"Corp code should be 8 digits: {info['corp_code']}")


class TestResolveTicker(unittest.TestCase):
    """Test resolve_ticker with various input formats."""

    def setUp(self):
        # Reset cache to use built-in data
        import tradingagents.dataflows.korea_ticker as kt
        kt._ticker_cache = None

    def test_resolve_by_stock_code(self):
        result = resolve_ticker("005930")
        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "005930")
        self.assertEqual(result["corp_code"], "00126380")
        self.assertEqual(result["name"], "삼성전자")

    def test_resolve_by_corp_code(self):
        result = resolve_ticker("00126380")
        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "005930")
        self.assertEqual(result["name"], "삼성전자")

    def test_resolve_by_korean_name(self):
        result = resolve_ticker("삼성전자")
        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "005930")

    def test_resolve_by_english_name(self):
        result = resolve_ticker("NAVER")
        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "035420")

    def test_resolve_by_english_name_case_insensitive(self):
        result = resolve_ticker("kakao")
        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "035720")

    def test_resolve_partial_name(self):
        result = resolve_ticker("현대자동차")
        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "005380")

    def test_resolve_not_found(self):
        result = resolve_ticker("존재하지않는회사XYZ")
        self.assertIsNone(result)

    def test_resolve_strips_whitespace(self):
        result = resolve_ticker("  005930  ")
        self.assertIsNotNone(result)
        self.assertEqual(result["stock_code"], "005930")


class TestConvenienceFunctions(unittest.TestCase):

    def setUp(self):
        import tradingagents.dataflows.korea_ticker as kt
        kt._ticker_cache = None

    def test_get_corp_code(self):
        self.assertEqual(get_corp_code("005930"), "00126380")

    def test_get_corp_code_not_found(self):
        self.assertIsNone(get_corp_code("999999"))

    def test_get_stock_code_from_name(self):
        self.assertEqual(get_stock_code("삼성전자"), "005930")

    def test_get_stock_code_from_code(self):
        self.assertEqual(get_stock_code("005930"), "005930")

    def test_get_stock_code_from_exchange_qualified_symbol(self):
        self.assertEqual(get_stock_code("005930.KS"), "005930")

    def test_get_stock_code_not_found(self):
        self.assertIsNone(get_stock_code("없는회사"))


class TestInstrumentProfile(unittest.TestCase):

    def setUp(self):
        import tradingagents.dataflows.korea_ticker as kt
        kt._ticker_cache = None

    def test_profile_from_company_name(self):
        profile = get_instrument_profile("삼성전자")
        self.assertTrue(profile["resolved"])
        self.assertEqual(profile["stock_code"], "005930")
        self.assertEqual(profile["news_query"], "삼성전자")
        self.assertEqual(profile["yfinance_symbol"], "005930")

    def test_profile_from_exchange_qualified_symbol(self):
        profile = get_instrument_profile("005930.KS")
        self.assertTrue(profile["resolved"])
        self.assertEqual(profile["stock_code"], "005930")
        self.assertEqual(profile["yfinance_symbol"], "005930.KS")
        self.assertTrue(profile["has_exchange_suffix"])

    def test_profile_from_unknown_symbol(self):
        profile = get_instrument_profile("7203.T")
        self.assertFalse(profile["resolved"])
        self.assertEqual(profile["yfinance_symbol"], "7203.T")
        self.assertEqual(profile["structured_symbol"], "7203.T")

    def test_yfinance_candidates_for_korean_stock(self):
        self.assertEqual(
            get_yfinance_candidates("삼성전자", prefer_qualified=True),
            ["005930.KS", "005930.KQ", "005930"],
        )


class TestCacheOperations(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_patch = patch(
            "tradingagents.dataflows.korea_ticker.get_config",
            return_value={"data_cache_dir": self.tmpdir},
        )
        self.config_patch.start()
        import tradingagents.dataflows.korea_ticker as kt
        kt._ticker_cache = None

    def tearDown(self):
        self.config_patch.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        import tradingagents.dataflows.korea_ticker as kt
        kt._ticker_cache = None

    def test_save_and_load_cache(self):
        test_data = {
            "005930": {"corp_code": "00126380", "name": "삼성전자", "name_eng": "Samsung"},
        }
        _save_cache(test_data)

        import tradingagents.dataflows.korea_ticker as kt
        kt._ticker_cache = None

        loaded = _load_cache()
        self.assertEqual(loaded["005930"]["name"], "삼성전자")

    def test_load_cache_falls_back_to_builtin(self):
        loaded = _load_cache()
        self.assertIn("005930", loaded)
        self.assertEqual(loaded["005930"]["name"], "삼성전자")


class TestUpdateFromDart(unittest.TestCase):

    def test_raises_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                update_from_dart()
            self.assertIn("DART_API_KEY", str(ctx.exception))

    @patch("tradingagents.dataflows.korea_ticker.requests.get")
    @patch("tradingagents.dataflows.korea_ticker.get_config", return_value={"data_cache_dir": tempfile.mkdtemp()})
    def test_parses_corpcode_xml(self, mock_config, mock_get):
        """Test parsing of corpCode.xml from DART (zip containing XML)."""
        import io
        import zipfile

        # Create mock XML content
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<result>
<list>
<corp_code>00126380</corp_code>
<corp_name>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90</corp_name>
<stock_code>005930</stock_code>
<modify_date>20260315</modify_date>
</list>
<list>
<corp_code>00164779</corp_code>
<corp_name>SK\xed\x95\x98\xec\x9d\xb4\xeb\x8b\x89\xec\x8a\xa4</corp_name>
<stock_code>000660</stock_code>
<modify_date>20260315</modify_date>
</list>
<list>
<corp_code>99999999</corp_code>
<corp_name>\xeb\xb9\x84\xec\x83\x81\xec\x9e\xa5\xed\x9a\x8c\xec\x82\xac</corp_name>
<stock_code> </stock_code>
<modify_date>20260101</modify_date>
</list>
</result>"""

        # Create zip in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("CORPCODE.xml", xml_content)
        zip_bytes = zip_buffer.getvalue()

        mock_resp = MagicMock()
        mock_resp.content = zip_bytes
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "test_key"}):
            import tradingagents.dataflows.korea_ticker as kt
            kt._ticker_cache = None
            count = update_from_dart()

        # Should have 2 listed companies (비상장회사 excluded because empty stock_code)
        self.assertEqual(count, 2)


class TestDartEventsAutoResolve(unittest.TestCase):
    """Test that get_dart_events auto-resolves stock codes to corp_codes."""

    def setUp(self):
        import tradingagents.dataflows.korea_ticker as kt
        kt._ticker_cache = None

    @patch("tradingagents.dataflows.dart_api.get_dart_disclosures")
    def test_resolves_stock_code_to_corp_code(self, mock_discl):
        from tradingagents.dataflows.dart_api import get_dart_events

        mock_discl.return_value = "disclosures"
        get_dart_events("005930", "2026-01-01", "2026-03-27")

        # Should have been called with corp_code, not stock_code
        called_corp_code = mock_discl.call_args[0][0]
        self.assertEqual(called_corp_code, "00126380")

    @patch("tradingagents.dataflows.dart_api.get_dart_disclosures")
    def test_passes_corp_code_directly(self, mock_discl):
        from tradingagents.dataflows.dart_api import get_dart_events

        mock_discl.return_value = "disclosures"
        get_dart_events("00126380", "2026-01-01", "2026-03-27")

        called_corp_code = mock_discl.call_args[0][0]
        self.assertEqual(called_corp_code, "00126380")

    @patch("tradingagents.dataflows.dart_api.get_dart_disclosures")
    def test_resolves_company_name(self, mock_discl):
        from tradingagents.dataflows.dart_api import get_dart_events

        mock_discl.return_value = "disclosures"
        get_dart_events("삼성전자", "2026-01-01", "2026-03-27")

        called_corp_code = mock_discl.call_args[0][0]
        self.assertEqual(called_corp_code, "00126380")


if __name__ == "__main__":
    unittest.main()
