"""Tests for the prefetch caching layer.

Verifies:
1. Cache key generation is deterministic
2. Cache miss returns None
3. Cache hit returns stored data
4. Today's data expires after TTL
5. Past date data never expires
6. clear_cache removes all cache files
7. _safe_fetch uses cache on second call (vendor not called twice)
8. Corrupt cache files are handled gracefully
"""

import json
import os
import tempfile
import time
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from tradingagents.dataflows.prefetch import (
    _cache_key,
    _cache_get,
    _cache_set,
    _safe_fetch,
    _extract_trade_date,
    clear_cache,
    _CACHE_TTL_SECONDS,
)


class TestCacheKey(unittest.TestCase):
    """Test cache key generation."""

    def test_deterministic(self):
        k1 = _cache_key("get_stock_data", "005930", "2026-03-27")
        k2 = _cache_key("get_stock_data", "005930", "2026-03-27")
        self.assertEqual(k1, k2)

    def test_different_args_different_keys(self):
        k1 = _cache_key("get_stock_data", "005930", "2026-03-27")
        k2 = _cache_key("get_stock_data", "000660", "2026-03-27")
        self.assertNotEqual(k1, k2)

    def test_different_func_different_keys(self):
        k1 = _cache_key("get_stock_data", "005930", "2026-03-27")
        k2 = _cache_key("get_indicators", "005930", "2026-03-27")
        self.assertNotEqual(k1, k2)

    def test_key_is_string(self):
        k = _cache_key("func", "arg1")
        self.assertIsInstance(k, str)
        self.assertEqual(len(k), 16)

    def test_cache_identity_changes_key(self):
        k1 = _cache_key(
            "get_stock_data",
            "005930",
            "2026-03-27",
            cache_identity={"vendors": ["kis"]},
        )
        k2 = _cache_key(
            "get_stock_data",
            "005930",
            "2026-03-27",
            cache_identity={"vendors": ["yfinance"]},
        )
        self.assertNotEqual(k1, k2)


class TestCacheGetSet(unittest.TestCase):
    """Test cache read/write operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_patch = patch(
            "tradingagents.dataflows.prefetch.get_config",
            return_value={"data_cache_dir": self.tmpdir},
        )
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cache_miss(self):
        result = _cache_get("nonexistent_key", "2026-03-20")
        self.assertIsNone(result)

    def test_cache_set_and_get(self):
        _cache_set("test_key", "cached data here")
        result = _cache_get("test_key", "2026-03-20")
        self.assertEqual(result, "cached data here")

    def test_past_date_never_expires(self):
        key = "past_data"
        # Write entry with old timestamp
        cache_dir = os.path.join(self.tmpdir, "prefetch_cache")
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{key}.json")
        with open(path, "w") as f:
            json.dump({"ts": time.time() - 86400, "data": "old data"}, f)

        result = _cache_get(key, "2026-03-20")  # past date
        self.assertEqual(result, "old data")

    def test_today_data_expires(self):
        key = "today_data"
        today = datetime.now().strftime("%Y-%m-%d")
        cache_dir = os.path.join(self.tmpdir, "prefetch_cache")
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{key}.json")
        with open(path, "w") as f:
            json.dump({"ts": time.time() - _CACHE_TTL_SECONDS - 10, "data": "stale"}, f)

        result = _cache_get(key, today)
        self.assertIsNone(result)

    def test_today_data_fresh(self):
        key = "today_fresh"
        today = datetime.now().strftime("%Y-%m-%d")
        _cache_set(key, "fresh data")

        result = _cache_get(key, today)
        self.assertEqual(result, "fresh data")

    def test_corrupt_cache_returns_none(self):
        cache_dir = os.path.join(self.tmpdir, "prefetch_cache")
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, "corrupt.json")
        with open(path, "w") as f:
            f.write("not valid json{{{")

        result = _cache_get("corrupt", "2026-03-20")
        self.assertIsNone(result)


class TestClearCache(unittest.TestCase):
    """Test cache clearing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_patch = patch(
            "tradingagents.dataflows.prefetch.get_config",
            return_value={"data_cache_dir": self.tmpdir},
        )
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_clear_cache_removes_files(self):
        _cache_set("a", "data_a")
        _cache_set("b", "data_b")

        count = clear_cache()
        self.assertEqual(count, 2)

        self.assertIsNone(_cache_get("a", "2026-03-20"))
        self.assertIsNone(_cache_get("b", "2026-03-20"))

    def test_clear_empty_cache(self):
        count = clear_cache()
        self.assertEqual(count, 0)


class TestSafeFetchWithCache(unittest.TestCase):
    """Test that _safe_fetch uses cache properly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_patch = patch(
            "tradingagents.dataflows.prefetch.get_config",
            return_value={"data_cache_dir": self.tmpdir},
        )
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_second_call_uses_cache(self):
        call_count = [0]

        def mock_vendor(*args, **kwargs):
            call_count[0] += 1
            return "vendor data"

        # First call - vendor called
        result1 = _safe_fetch("Test", mock_vendor, "get_test", "005930", "2026-03-20")
        self.assertEqual(call_count[0], 1)
        self.assertIn("vendor data", result1)

        # Second call - should use cache, vendor NOT called again
        result2 = _safe_fetch("Test", mock_vendor, "get_test", "005930", "2026-03-20")
        self.assertEqual(call_count[0], 1)  # Still 1!
        self.assertEqual(result1, result2)

    def test_failed_fetch_not_cached(self):
        call_count = [0]

        def failing_vendor(*args, **kwargs):
            call_count[0] += 1
            raise ConnectionError("network down")

        result = _safe_fetch("Fail", failing_vendor, "get_test", "005930", "2026-03-20")
        self.assertIn("[Data unavailable:", result)
        self.assertEqual(call_count[0], 1)

        # Second call should retry (not cached)
        result2 = _safe_fetch("Fail", failing_vendor, "get_test", "005930", "2026-03-20")
        self.assertEqual(call_count[0], 2)

    def test_cache_identity_prevents_stale_reuse(self):
        call_count = [0]

        def mock_vendor(*args, **kwargs):
            call_count[0] += 1
            return f"vendor data #{call_count[0]}"

        result1 = _safe_fetch(
            "Test",
            mock_vendor,
            "get_test",
            "005930",
            "2026-03-20",
            cache_identity={"vendors": ["kis"]},
        )
        result2 = _safe_fetch(
            "Test",
            mock_vendor,
            "get_test",
            "005930",
            "2026-03-20",
            cache_identity={"vendors": ["yfinance"]},
        )

        self.assertEqual(call_count[0], 2)
        self.assertNotEqual(result1, result2)


class TestExtractTradeDate(unittest.TestCase):
    """Test trade date extraction from args."""

    def test_extracts_date_string(self):
        result = _extract_trade_date(("get_stock_data", "005930", "2026-03-27"))
        self.assertEqual(result, "2026-03-27")

    def test_skips_non_date_strings(self):
        result = _extract_trade_date(("get_indicators", "005930", "rsi", "2026-03-27", 30))
        self.assertEqual(result, "2026-03-27")

    def test_defaults_to_today_when_no_date(self):
        result = _extract_trade_date(("no", "dates", "here"))
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(result, today)


if __name__ == "__main__":
    unittest.main()
