import unittest
from datetime import date

from tradingagents.dataflows.kis_vendor import add_trading_days, is_trading_day


class TestKisTradingDays(unittest.TestCase):
    def test_add_trading_days_skips_weekend_with_weekday_fallback(self):
        # Tue 2026-06-23, empty calendar -> weekday heuristic skips Sat/Sun.
        result = add_trading_days(date(2026, 6, 23), 5, holidays={})
        self.assertEqual(result, date(2026, 6, 30))  # Wed/Thu/Fri/Mon/Tue -> Tue 6/30

    def test_add_trading_days_skips_holiday_from_calendar(self):
        # Mark Thu 2026-06-25 as a market holiday; it should be skipped.
        holidays = {date(2026, 6, 25): False}
        result = add_trading_days(date(2026, 6, 23), 3, holidays=holidays)
        # open days after Tue 6/23: Wed 6/24, (Thu 6/25 closed), Fri 6/26, Mon 6/29
        self.assertEqual(result, date(2026, 6, 29))

    def test_add_trading_days_zero_returns_start(self):
        self.assertEqual(add_trading_days(date(2026, 6, 23), 0, holidays={}), date(2026, 6, 23))

    def test_is_trading_day_uses_calendar_then_weekday(self):
        self.assertFalse(is_trading_day(date(2026, 6, 27), holidays={}))  # Saturday
        self.assertTrue(is_trading_day(date(2026, 6, 26), holidays={}))   # Friday
        self.assertFalse(is_trading_day(date(2026, 6, 25), holidays={date(2026, 6, 25): False}))


if __name__ == "__main__":
    unittest.main()
