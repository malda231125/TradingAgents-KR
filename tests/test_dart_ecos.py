"""Tests for Open DART and ECOS API modules.

Mock responses use actual JSON structures from official API documentation:
- DART: https://opendart.fss.or.kr/guide/main.do
- ECOS: https://ecos.bok.or.kr/api/
- ECOS sample key responses verified on 2026-03-27

Verifies:
1. DART credential check, request building, response parsing, error handling
2. DART disclosure search, company info, financial statements
3. ECOS credential check, date format conversion, response parsing
4. ECOS StatisticSearch and KeyStatisticList paths
5. ECOS macro summary with fallback logic
6. Vendor registration in interface.py
"""

import unittest
from unittest.mock import patch, MagicMock, call

from tradingagents.dataflows.dart_api import (
    _dart_available,
    _dart_request,
    get_dart_disclosures,
    get_dart_company_info,
    get_dart_financial_statements,
    get_dart_events,
)
from tradingagents.dataflows.ecos_api import (
    _ecos_available,
    _ecos_request,
    get_ecos_stat,
    get_korea_macro_summary,
    MACRO_STAT_CODES,
)
from tradingagents.dataflows.interface import VENDOR_METHODS, VENDOR_LIST, TOOLS_CATEGORIES


# ============================================================
# DART Tests
# ============================================================

class TestDartAvailability(unittest.TestCase):

    def test_unavailable_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_dart_available())

    def test_available_with_key(self):
        with patch.dict("os.environ", {"DART_API_KEY": "abc123"}):
            self.assertTrue(_dart_available())


class TestDartRequest(unittest.TestCase):
    """Test the low-level _dart_request function."""

    def test_raises_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                _dart_request("list", {"corp_code": "00126380"})
            self.assertIn("DART API key not configured", str(ctx.exception))

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_sends_crtfc_key_param(self, mock_get):
        """API key must be sent as crtfc_key query parameter."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "000", "list": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "MY_KEY_123"}):
            _dart_request("list", {"corp_code": "00126380"})

        call_kwargs = mock_get.call_args
        self.assertIn("crtfc_key", call_kwargs.kwargs.get("params", {}))
        self.assertEqual(call_kwargs.kwargs["params"]["crtfc_key"], "MY_KEY_123")

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_url_format(self, mock_get):
        """URL should be base_url/endpoint.json"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "000"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            _dart_request("company", {"corp_code": "00126380"})

        url = mock_get.call_args[0][0]
        self.assertTrue(url.endswith("/company.json"))

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_status_010_raises(self, mock_get):
        """Status 010 = unregistered key → should raise."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "010", "message": "등록되지 않은 인증키입니다."}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "bad_key"}):
            with self.assertRaises(RuntimeError) as ctx:
                _dart_request("list", {})
            self.assertIn("등록되지 않은 인증키", str(ctx.exception))

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_status_013_returns_empty(self, mock_get):
        """Status 013 = no data → should return empty list, not raise."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "013", "message": "조회된 데이터가 없습니다."}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            result = _dart_request("list", {})
            self.assertEqual(result["list"], [])

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_network_error_raises(self, mock_get):
        """Network failures should raise RuntimeError."""
        import requests as req
        mock_get.side_effect = req.ConnectionError("timeout")

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            with self.assertRaises(RuntimeError) as ctx:
                _dart_request("list", {})
            self.assertIn("DART API request failed", str(ctx.exception))


class TestDartDisclosures(unittest.TestCase):
    """Test disclosure search with official doc response format."""

    # Response format from DART docs: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=A001
    MOCK_DISCLOSURE_RESPONSE = {
        "status": "000",
        "message": "정상",
        "page_no": 1,
        "page_count": 10,
        "total_count": 3,
        "total_page": 1,
        "list": [
            {
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "stock_code": "005930",
                "corp_cls": "Y",
                "report_nm": "[기재정정]사업보고서 (2025.12)",
                "rcept_no": "20260315000123",
                "flr_nm": "삼성전자",
                "rcept_dt": "20260315",
                "rm": "유",
            },
            {
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "stock_code": "005930",
                "corp_cls": "Y",
                "report_nm": "분기보고서 (2026.03)",
                "rcept_no": "20260310000456",
                "flr_nm": "삼성전자",
                "rcept_dt": "20260310",
                "rm": "",
            },
        ],
    }

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_parses_real_format(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self.MOCK_DISCLOSURE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            result = get_dart_disclosures("00126380", "2026-01-01", "2026-03-27")

        self.assertIn("삼성전자", result)
        self.assertIn("[기재정정]사업보고서", result)
        self.assertIn("분기보고서", result)
        self.assertIn("20260315", result)
        # Classified output groups by impact
        self.assertIn("정기 보고서", result)

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_date_format_conversion(self, mock_get):
        """Dates should be sent as yyyymmdd (no dashes)."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "000", "list": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            get_dart_disclosures("00126380", "2026-01-01", "2026-03-27")

        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["bgn_de"], "20260101")
        self.assertEqual(params["end_de"], "20260327")


class TestDartCompanyInfo(unittest.TestCase):
    """Test company info with official doc response format."""

    MOCK_COMPANY_RESPONSE = {
        "status": "000",
        "corp_code": "00126380",
        "corp_name": "삼성전자",
        "corp_name_eng": "SAMSUNG ELECTRONICS CO.,LTD",
        "stock_name": "삼성전자",
        "stock_code": "005930",
        "ceo_nm": "한종희, 경계현",
        "corp_cls": "Y",
        "est_dt": "19690113",
        "acc_mt": "12",
        "induty_code": "264",
    }

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_parses_company_info(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self.MOCK_COMPANY_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            result = get_dart_company_info("00126380")

        self.assertIn("삼성전자", result)
        self.assertIn("SAMSUNG ELECTRONICS", result)
        self.assertIn("005930", result)
        self.assertIn("한종희", result)


class TestDartFinancialStatements(unittest.TestCase):
    """Test financial statements with official doc response format."""

    MOCK_FS_RESPONSE = {
        "status": "000",
        "list": [
            {
                "rcept_no": "20260401000001",
                "reprt_code": "11013",
                "bsns_year": "2026",
                "corp_code": "00126380",
                "sj_div": "BS",
                "sj_nm": "재무상태표",
                "account_id": "ifrs-full_Assets",
                "account_nm": "자산총계",
                "account_detail": "-",
                "thstrm_nm": "제 58 기 1분기말",
                "thstrm_amount": "486,345,678,000,000",
                "frmtrm_nm": "제 57 기말",
                "frmtrm_amount": "478,123,456,000,000",
                "ord": "1",
            },
            {
                "rcept_no": "20260401000001",
                "reprt_code": "11013",
                "bsns_year": "2026",
                "corp_code": "00126380",
                "sj_div": "IS",
                "sj_nm": "손익계산서",
                "account_id": "ifrs-full_Revenue",
                "account_nm": "매출액",
                "account_detail": "-",
                "thstrm_nm": "제 58 기 1분기",
                "thstrm_amount": "78,456,789,000,000",
                "frmtrm_nm": "제 57 기 1분기",
                "frmtrm_amount": "71,234,567,000,000",
                "ord": "1",
            },
        ],
    }

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_parses_financial_statements(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self.MOCK_FS_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            result = get_dart_financial_statements("00126380", "2026", "11013")

        self.assertIn("자산총계", result)
        self.assertIn("매출액", result)
        self.assertIn("재무상태표", result)
        self.assertIn("손익계산서", result)
        self.assertIn("486,345,678,000,000", result)

    @patch("tradingagents.dataflows.dart_api.requests.get")
    def test_report_code_labels(self, mock_get):
        """Report code should map to readable labels when data exists."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "000",
            "list": [{"sj_nm": "재무상태표", "account_nm": "자산총계", "thstrm_amount": "100", "frmtrm_amount": "90"}],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"DART_API_KEY": "key"}):
            result = get_dart_financial_statements("00126380", "2026", "11011")
        self.assertIn("Annual", result)


class TestDartEvents(unittest.TestCase):
    """Test the interface-compatible get_dart_events function."""

    @patch("tradingagents.dataflows.dart_api.get_dart_disclosures")
    def test_delegates_to_disclosures(self, mock_discl):
        mock_discl.return_value = "disclosure data"
        result = get_dart_events("00126380", "2026-01-01", "2026-03-27")
        self.assertEqual(result, "disclosure data")
        mock_discl.assert_called_once_with("00126380", "2026-01-01", "2026-03-27")


# ============================================================
# ECOS Tests
# ============================================================

class TestEcosAvailability(unittest.TestCase):

    def test_unavailable_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_ecos_available())

    def test_available_with_key(self):
        with patch.dict("os.environ", {"ECOS_API_KEY": "test_key"}):
            self.assertTrue(_ecos_available())


class TestEcosRequest(unittest.TestCase):
    """Test _ecos_request URL building and date format handling."""

    def test_raises_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                _ecos_request("StatisticSearch", "722Y001", "M", "2026-01-01", "2026-03-27", "0101000")

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_monthly_date_format(self, mock_get):
        """Monthly cycle should use YYYYMM dates."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"StatisticSearch": {"row": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            _ecos_request("StatisticSearch", "722Y001", "M", "2026-01-15", "2026-03-27", "0101000")

        url = mock_get.call_args[0][0]
        # Should contain YYYYMM not YYYYMMDD
        self.assertIn("/202601/", url)
        self.assertIn("/202603/", url)
        self.assertNotIn("/20260115/", url)

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_daily_date_format(self, mock_get):
        """Daily cycle should use YYYYMMDD dates."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"StatisticSearch": {"row": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            _ecos_request("StatisticSearch", "731Y003", "D", "2026-03-20", "2026-03-27", "0000001")

        url = mock_get.call_args[0][0]
        self.assertIn("/20260320/", url)
        self.assertIn("/20260327/", url)

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_annual_date_format(self, mock_get):
        """Annual cycle should use YYYY dates."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"StatisticSearch": {"row": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            _ecos_request("StatisticSearch", "TEST", "A", "2024-01-01", "2026-12-31", "ITEM")

        url = mock_get.call_args[0][0]
        self.assertIn("/2024/", url)
        self.assertIn("/2026/", url)

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_api_key_in_url_path(self, mock_get):
        """ECOS uses path-based auth, not query param."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"StatisticSearch": {"row": []}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "MY_ECOS_KEY"}):
            _ecos_request("StatisticSearch", "722Y001", "M", "2026-01-01", "2026-03-27", "0101000")

        url = mock_get.call_args[0][0]
        self.assertIn("/MY_ECOS_KEY/", url)

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_info_200_returns_empty(self, mock_get):
        """INFO-200 = no data → should return empty rows, not raise."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            result = _ecos_request("StatisticSearch", "731Y003", "D", "2026-03-20", "2026-03-27", "0000001")
            self.assertEqual(result["StatisticSearch"]["row"], [])

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_other_error_raises(self, mock_get):
        """Non-INFO-000/INFO-200 errors should raise."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "RESULT": {"CODE": "ERROR-100", "MESSAGE": "서버 오류입니다."}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            with self.assertRaises(RuntimeError) as ctx:
                _ecos_request("StatisticSearch", "TEST", "M", "2026-01-01", "2026-03-27", "ITEM")
            self.assertIn("서버 오류", str(ctx.exception))


class TestEcosStatisticSearch(unittest.TestCase):
    """Test get_ecos_stat with actual ECOS response format (verified with sample key)."""

    # Actual response from: /api/StatisticSearch/sample/json/kr/1/5/722Y001/M/202601/202603/0101000
    MOCK_BASE_RATE_RESPONSE = {
        "StatisticSearch": {
            "list_total_count": 2,
            "row": [
                {
                    "STAT_CODE": "722Y001",
                    "STAT_NAME": "1.3.1. 한국은행 기준금리 및 여수신금리",
                    "ITEM_CODE1": "0101000",
                    "ITEM_NAME1": "한국은행 기준금리",
                    "ITEM_CODE2": None,
                    "ITEM_NAME2": None,
                    "UNIT_NAME": "연%",
                    "TIME": "202601",
                    "DATA_VALUE": "2.5",
                },
                {
                    "STAT_CODE": "722Y001",
                    "STAT_NAME": "1.3.1. 한국은행 기준금리 및 여수신금리",
                    "ITEM_CODE1": "0101000",
                    "ITEM_NAME1": "한국은행 기준금리",
                    "ITEM_CODE2": None,
                    "ITEM_NAME2": None,
                    "UNIT_NAME": "연%",
                    "TIME": "202602",
                    "DATA_VALUE": "2.5",
                },
            ],
        }
    }

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_parses_real_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = self.MOCK_BASE_RATE_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            result = get_ecos_stat("722Y001", "0101000", "M", "2026-01-01", "2026-03-27")

        self.assertIn("한국은행 기준금리", result)
        self.assertIn("2.5", result)
        self.assertIn("연%", result)
        self.assertIn("202601", result)
        self.assertIn("202602", result)


class TestEcosMacroSummary(unittest.TestCase):
    """Test get_korea_macro_summary with both KeyStatisticList and fallback paths."""

    # Actual KeyStatisticList response (verified with sample key 2026-03-27)
    MOCK_KEY_STAT_RESPONSE = {
        "KeyStatisticList": {
            "list_total_count": 101,
            "row_count": 10,
            "row": [
                {"CLASS_NAME": "통화량", "KEYSTAT_NAME": "M1(협의통화, 평잔)", "DATA_VALUE": "1344634.7", "CYCLE": "202601", "UNIT_NAME": "십억원"},
                {"CLASS_NAME": "통화량", "KEYSTAT_NAME": "M2(광의통화, 평잔)", "DATA_VALUE": "4101033.6", "CYCLE": "202601", "UNIT_NAME": "십억원"},
                {"CLASS_NAME": "환율", "KEYSTAT_NAME": "원/달러 환율(종가)", "DATA_VALUE": "1508.9", "CYCLE": "20260327", "UNIT_NAME": "원"},
                {"CLASS_NAME": "환율", "KEYSTAT_NAME": "원/엔(100엔) 환율(매매기준율)", "DATA_VALUE": "943.47", "CYCLE": "20260327", "UNIT_NAME": "원"},
                {"CLASS_NAME": "환율", "KEYSTAT_NAME": "원/유로 환율(매매기준율)", "DATA_VALUE": "1737.93", "CYCLE": "20260327", "UNIT_NAME": "원"},
                {"CLASS_NAME": "소득", "KEYSTAT_NAME": "GDP(명목, 계절조정)", "DATA_VALUE": "690599.9", "CYCLE": "2025Q4", "UNIT_NAME": "십억원"},
            ],
        }
    }

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_key_stat_list_path(self, mock_get):
        """When KeyStatisticList succeeds, use it directly."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = self.MOCK_KEY_STAT_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            result = get_korea_macro_summary("2026-03-27")

        self.assertIn("주요 경제지표", result)
        self.assertIn("원/달러 환율", result)
        self.assertIn("1508.9", result)
        self.assertIn("M2(광의통화", result)
        self.assertIn("GDP", result)

    @patch("tradingagents.dataflows.ecos_api.requests.get")
    def test_fallback_to_individual_search(self, mock_get):
        """When KeyStatisticList fails, fall back to StatisticSearch per indicator."""
        call_count = [0]

        def side_effect(url, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()

            if "KeyStatisticList" in url:
                # Simulate KeyStatisticList failure
                import requests as req
                raise req.ConnectionError("timeout")
            else:
                # Individual StatisticSearch succeeds
                mock_resp.json.return_value = {
                    "StatisticSearch": {
                        "row": [{
                            "STAT_NAME": "test",
                            "ITEM_NAME1": "test",
                            "TIME": "202603",
                            "DATA_VALUE": "99.9",
                            "UNIT_NAME": "%",
                        }]
                    }
                }
            return mock_resp

        mock_get.side_effect = side_effect

        with patch.dict("os.environ", {"ECOS_API_KEY": "key"}):
            result = get_korea_macro_summary("2026-03-27")

        self.assertIn("개별 조회", result)
        # Should have called KeyStatisticList once + individual searches
        self.assertGreater(call_count[0], 1)

    def test_macro_stat_codes_complete(self):
        """All expected macro codes should be defined."""
        expected = {"base_rate", "usd_krw", "kospi", "cpi", "m2"}
        self.assertEqual(set(MACRO_STAT_CODES.keys()), expected)

        for key, spec in MACRO_STAT_CODES.items():
            self.assertIn("stat_code", spec)
            self.assertIn("item_code", spec)
            self.assertIn("cycle", spec)
            self.assertIn("label", spec)


# ============================================================
# Interface Registration Tests
# ============================================================

class TestInterfaceRegistration(unittest.TestCase):

    def test_dart_in_vendor_list(self):
        self.assertIn("dart", VENDOR_LIST)

    def test_ecos_in_vendor_list(self):
        self.assertIn("ecos", VENDOR_LIST)

    def test_dart_in_insider_transactions(self):
        self.assertIn("dart", VENDOR_METHODS["get_insider_transactions"])

    def test_ecos_in_macro_summary(self):
        self.assertIn("ecos", VENDOR_METHODS["get_macro_summary"])

    def test_macro_data_category_exists(self):
        self.assertIn("macro_data", TOOLS_CATEGORIES)
        self.assertIn("get_macro_summary", TOOLS_CATEGORIES["macro_data"]["tools"])

    def test_dart_is_first_in_insider_transactions(self):
        """DART should be preferred over yfinance/alpha_vantage for Korean disclosures."""
        vendors = list(VENDOR_METHODS["get_insider_transactions"].keys())
        self.assertEqual(vendors[0], "dart")


if __name__ == "__main__":
    unittest.main()
