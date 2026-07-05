"""Tests for the KIS sector index code mapping module.

These tests pin down the static mapping so that accidental edits to
sector_index.py do not silently break the packet builder.
"""

import pytest

from tradingagents.dataflows.sector_index import (
    KIS_SECTOR_INDEX_CODES,
    STOCK_TO_SECTOR,
    get_sector_for_stock,
    get_sector_index_code,
    get_sector_index_code_for_stock,
)


class TestKISSectorIndexCodes:
    """Pin specific known-good codes verified against idxcode.mst."""

    def test_kospi_composite(self):
        assert KIS_SECTOR_INDEX_CODES["KOSPI 종합"] == "0001"

    def test_kospi_200(self):
        assert KIS_SECTOR_INDEX_CODES["KOSPI 200"] == "2001"

    def test_kosdaq_composite(self):
        assert KIS_SECTOR_INDEX_CODES["KOSDAQ 종합"] == "1001"

    def test_krx_semiconductor(self):
        assert KIS_SECTOR_INDEX_CODES["KRX 반도체"] == "4003"

    def test_krx_bank(self):
        assert KIS_SECTOR_INDEX_CODES["KRX 은행"] == "4005"

    def test_krx_automobile(self):
        assert KIS_SECTOR_INDEX_CODES["KRX 자동차"] == "4002"

    def test_k200_information_technology(self):
        assert KIS_SECTOR_INDEX_CODES["K200 정보기술"] == "2013"

    def test_all_codes_are_4_digit_strings(self):
        for name, code in KIS_SECTOR_INDEX_CODES.items():
            assert isinstance(code, str), f"{name}: code must be str"
            assert len(code) == 4, f"{name}: code must be 4 chars, got {code!r}"
            assert code.isdigit(), f"{name}: code must be digits, got {code!r}"


class TestStockToSectorMapping:
    """Spot-check the curated stock → sector mapping."""

    def test_samsung_electronics(self):
        assert STOCK_TO_SECTOR["005930"] == "KRX 반도체"

    def test_sk_hynix(self):
        assert STOCK_TO_SECTOR["000660"] == "KRX 반도체"

    def test_kb_financial(self):
        assert STOCK_TO_SECTOR["105560"] == "KRX 은행"

    def test_naver(self):
        assert STOCK_TO_SECTOR["035420"] == "K200 정보기술"

    def test_hyundai_motor(self):
        assert STOCK_TO_SECTOR["005380"] == "KRX 자동차"

    def test_lg_chem(self):
        assert STOCK_TO_SECTOR["051910"] == "KRX 에너지화학"

    def test_celltrion(self):
        assert STOCK_TO_SECTOR["068270"] == "KRX 헬스케어"

    def test_every_stock_resolves_to_a_known_sector_code(self):
        """No mapping entry should reference a sector that doesn't exist in the index code dict."""
        for stock_code, sector_name in STOCK_TO_SECTOR.items():
            assert sector_name in KIS_SECTOR_INDEX_CODES, (
                f"stock {stock_code} maps to unknown sector '{sector_name}'"
            )

    def test_all_stock_codes_are_6_digit_strings(self):
        for stock_code in STOCK_TO_SECTOR:
            assert isinstance(stock_code, str)
            assert len(stock_code) == 6, f"stock_code must be 6 chars, got {stock_code!r}"
            assert stock_code.isdigit(), f"stock_code must be digits, got {stock_code!r}"


class TestGetSectorForStock:
    def test_known_stock_returns_sector_name(self):
        assert get_sector_for_stock("005930") == "KRX 반도체"

    def test_unknown_stock_returns_none(self):
        assert get_sector_for_stock("999999") is None

    def test_empty_string_returns_none(self):
        assert get_sector_for_stock("") is None

    def test_none_returns_none(self):
        assert get_sector_for_stock(None) is None

    def test_whitespace_is_stripped(self):
        assert get_sector_for_stock("  005930  ") == "KRX 반도체"


class TestGetSectorIndexCode:
    def test_known_sector_returns_code(self):
        assert get_sector_index_code("KRX 반도체") == "4003"

    def test_unknown_sector_returns_none(self):
        assert get_sector_index_code("does not exist") is None

    def test_empty_string_returns_none(self):
        assert get_sector_index_code("") is None


class TestGetSectorIndexCodeForStock:
    def test_known_stock_returns_tuple(self):
        result = get_sector_index_code_for_stock("005930")
        assert result == ("KRX 반도체", "4003")

    def test_kb_financial_returns_bank(self):
        result = get_sector_index_code_for_stock("105560")
        assert result == ("KRX 은행", "4005")

    def test_unknown_stock_returns_none(self):
        assert get_sector_index_code_for_stock("999999") is None

    def test_empty_returns_none(self):
        assert get_sector_index_code_for_stock("") is None
