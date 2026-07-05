"""Tests for the deterministic SignalProcessor regex extractor."""

import pytest

from tradingagents.graph.signal_processing import SignalProcessor, extract_rating


class TestExplicitRatingLine:
    """Cases where the LLM produces a `Rating: X` line per the prompt template."""

    def test_bold_markdown_rating_buy(self):
        text = "1. **Rating**: Buy\n2. Executive Summary: ..."
        assert extract_rating(text) == "BUY"

    def test_bold_markdown_rating_overweight(self):
        text = "**Rating**: Overweight\n**Executive Summary**: ..."
        assert extract_rating(text) == "OVERWEIGHT"

    def test_plain_rating_hold(self):
        text = "Rating: Hold\nExecutive Summary: maintain position"
        assert extract_rating(text) == "HOLD"

    def test_underweight(self):
        text = "**Rating**: Underweight"
        assert extract_rating(text) == "UNDERWEIGHT"

    def test_sell(self):
        text = "Rating: Sell — exit immediately"
        assert extract_rating(text) == "SELL"

    def test_rating_value_also_bolded(self):
        text = "**Rating**: **Buy**"
        assert extract_rating(text) == "BUY"

    def test_korean_rating_label(self):
        text = "Rating: 매수\n이유: ..."
        assert extract_rating(text) == "BUY"

    def test_korean_jung_rip_maps_to_hold(self):
        text = "Rating: 중립"
        assert extract_rating(text) == "HOLD"

    def test_takes_last_explicit_rating_when_multiple(self):
        # The LLM might restate the rating multiple times; the FINAL one wins.
        text = "Initial assessment Rating: Hold\n\n... revised conclusion ...\n**Rating**: Sell"
        assert extract_rating(text) == "SELL"

    def test_section_style_rating_on_next_line(self):
        text = "**1. Rating**\n**Underweight**\n\n**2. Executive Summary**\n..."
        assert extract_rating(text) == "UNDERWEIGHT"


class TestFallbackToken:
    """Cases without an explicit Rating line — last bare token wins."""

    def test_bare_token_in_paragraph(self):
        text = "After review, the recommendation is to Hold the position."
        assert extract_rating(text) == "HOLD"

    def test_takes_last_bare_token(self):
        text = "Initially considered a Buy, but after risk analysis we recommend Sell."
        assert extract_rating(text) == "SELL"

    def test_korean_bare_token(self):
        text = "최종 결론: 매도가 적절하다."
        assert extract_rating(text) == "SELL"

    def test_korean_substring_does_not_override_section_rating(self):
        text = """
        **1. Rating**
        **Underweight**

        **4. Key Risk Triggers**
        외국인 순매수가 2~3거래일 이상 붙으면 판단을 철회합니다.
        """
        assert extract_rating(text) == "UNDERWEIGHT"


class TestEdgeCases:
    def test_empty_string_defaults_hold(self):
        assert extract_rating("") == "HOLD"

    def test_none_defaults_hold(self):
        assert extract_rating(None) == "HOLD"

    def test_unrelated_text_defaults_hold(self):
        text = "The model could not produce a clear judgment."
        assert extract_rating(text) == "HOLD"

    def test_explicit_rating_outranks_bare_token(self):
        # A bare 'Sell' word in supporting text must NOT override an explicit
        # `Rating: Buy` line.
        text = "We weighed the risk of a Sell signal but the explicit decision is:\nRating: Buy"
        assert extract_rating(text) == "BUY"


class TestSignalProcessorClass:
    def test_class_delegates_to_extract_rating(self):
        sp = SignalProcessor(quick_thinking_llm=None)
        assert sp.process_signal("**Rating**: Overweight") == "OVERWEIGHT"

    def test_constructor_accepts_legacy_llm_arg(self):
        # Backwards compatibility: TradingAgentsGraph constructs
        # SignalProcessor(self.quick_thinking_llm). The argument is ignored
        # but must not raise.
        SignalProcessor(quick_thinking_llm="anything")
