"""Tests for the NLU-driven news feature packet enricher."""

import json
from unittest.mock import MagicMock

import pytest

from tradingagents.dataflows.feature_packets.news import (
    NewsPacket,
    _extract_json_object,
    _normalize_catalyst,
    _slugify,
    build_news_packet_from_text,
)


SAMSUNG_INSTRUMENT = {"name": "삼성전자", "stock_code": "005930"}


def _make_llm(response_text: str):
    """Build a minimal mock LLM that returns a fixed string from .invoke()."""
    mock = MagicMock()
    response = MagicMock()
    response.content = response_text
    mock.invoke.return_value = response
    return mock


# ----------------------------------------------------------------------
# JSON extraction
# ----------------------------------------------------------------------


class TestExtractJsonObject:
    def test_fenced_json_block(self):
        text = 'Sure, here you go:\n```json\n{"a": 1, "b": [2, 3]}\n```\nThanks!'
        out = _extract_json_object(text)
        assert out == {"a": 1, "b": [2, 3]}

    def test_unfenced_json_object(self):
        text = 'Result: {"a": 1, "b": "two"}'
        out = _extract_json_object(text)
        assert out == {"a": 1, "b": "two"}

    def test_returns_none_on_garbage(self):
        assert _extract_json_object("not json at all") is None
        assert _extract_json_object("") is None
        assert _extract_json_object(None) is None

    def test_nested_object_balanced(self):
        text = '{"outer": {"inner": [1, 2, {"k": "v"}]}}'
        out = _extract_json_object(text)
        assert out == {"outer": {"inner": [1, 2, {"k": "v"}]}}

    def test_picks_first_complete_object(self):
        text = "noise {bad json} then ```json\n{\"good\": true}\n```"
        out = _extract_json_object(text)
        assert out == {"good": True}


# ----------------------------------------------------------------------
# Catalyst normalization
# ----------------------------------------------------------------------


class TestNormalizeCatalyst:
    def test_well_formed_catalyst(self):
        raw = {
            "id": "block_deal",
            "type": "event",
            "title": "홍라희 블록딜",
            "summary": "상속세 매각으로 단기 수급 부담",
            "expected_impact": "short_term_negative",
            "confidence": "high",
            "sources": ["naver", "yfinance"],
        }
        out = _normalize_catalyst(raw)
        assert out["id"] == "block_deal"
        assert out["type"] == "event"
        assert out["expected_impact"] == "short_term_negative"
        assert out["confidence"] == "high"
        assert out["sources"] == ["naver", "yfinance"]

    def test_invalid_type_falls_back_to_event(self):
        raw = {"title": "x", "type": "bogus"}
        out = _normalize_catalyst(raw)
        assert out["type"] == "event"

    def test_invalid_impact_falls_back_to_neutral(self):
        raw = {"title": "x", "expected_impact": "rocket"}
        out = _normalize_catalyst(raw)
        assert out["expected_impact"] == "neutral"

    def test_invalid_confidence_falls_back_to_medium(self):
        raw = {"title": "x", "confidence": "extreme"}
        out = _normalize_catalyst(raw)
        assert out["confidence"] == "medium"

    def test_missing_title_drops_catalyst(self):
        raw = {"type": "event"}
        assert _normalize_catalyst(raw) is None

    def test_non_dict_drops_catalyst(self):
        assert _normalize_catalyst("not a dict") is None
        assert _normalize_catalyst(None) is None

    def test_missing_id_is_slugified_from_title(self):
        raw = {"title": "삼성전자 AI 칩 호조"}
        out = _normalize_catalyst(raw)
        assert out["id"]
        assert "_" in out["id"] or out["id"] != "catalyst"  # got something meaningful

    def test_string_source_normalizes_to_list(self):
        raw = {"title": "x", "sources": "naver"}
        out = _normalize_catalyst(raw)
        assert out["sources"] == ["naver"]


class TestSlugify:
    def test_korean_title_slugified(self):
        s = _slugify("삼성전자 AI 칩 호조 보고")
        assert s
        assert " " not in s

    def test_empty_falls_back(self):
        assert _slugify("") == "catalyst"

    def test_truncation(self):
        s = _slugify("A" * 100, max_len=10)
        assert len(s) <= 10


# ----------------------------------------------------------------------
# build_news_packet_from_text — happy path
# ----------------------------------------------------------------------


_VALID_LLM_RESPONSE = """\
Here is the structured packet:

```json
{
  "company_catalysts": [
    {
      "id": "owner_share_sale",
      "type": "event",
      "title": "홍라희 블록딜 및 상속세 매각",
      "summary": "오너 일가의 상속세 관련 매각으로 단기 수급 부담이 발생",
      "expected_impact": "short_term_negative",
      "confidence": "high",
      "sources": ["naver"]
    },
    {
      "id": "ai_chip_outlook",
      "type": "fundamental",
      "title": "AI 반도체 수요 기반 실적 개선 전망",
      "summary": "HBM 수요 확장으로 중기 실적 개선 narrative 강화",
      "expected_impact": "medium_term_positive",
      "confidence": "medium",
      "sources": ["yfinance"]
    }
  ],
  "macro_news": [
    {"title": "원/달러 환율 급등", "expected_effect": "외국인 매도 압력 가능"}
  ],
  "noise_count": 8,
  "notes": ["일부 기사가 단일 소스에만 의존"]
}
```
"""


class TestBuildNewsPacketHappyPath:
    def test_parses_well_formed_response(self):
        llm = _make_llm(_VALID_LLM_RESPONSE)

        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="(some 10k chars of raw articles here)" * 100,
            llm=llm,
            evidence_refs=["news:raw:005930:2026-04-10"],
        )

        assert isinstance(packet, NewsPacket)
        assert packet.instrument == SAMSUNG_INSTRUMENT
        assert packet.as_of == "2026-04-10"
        assert len(packet.company_catalysts) == 2
        assert packet.company_catalysts[0]["id"] == "owner_share_sale"
        assert packet.company_catalysts[0]["expected_impact"] == "short_term_negative"
        assert packet.company_catalysts[1]["type"] == "fundamental"
        assert len(packet.macro_news) == 1
        assert packet.noise_count == 8
        assert packet.evidence_refs == ["news:raw:005930:2026-04-10"]
        assert "단일 소스" in packet.data_quality_notes[0]

    def test_packet_serializes_to_prompt_block(self):
        llm = _make_llm(_VALID_LLM_RESPONSE)
        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="x" * 200,
            llm=llm,
        )
        block = packet.to_prompt_block()
        assert block.startswith("```json")
        assert block.endswith("```")

        body = block.strip("`").lstrip("json").strip()
        parsed = json.loads(body)
        assert parsed["instrument"]["stock_code"] == "005930"
        assert "company_catalysts" in parsed
        assert "noise_count" in parsed


# ----------------------------------------------------------------------
# build_news_packet_from_text — degenerate / failure cases
# ----------------------------------------------------------------------


class TestBuildNewsPacketEdgeCases:
    def test_empty_raw_news_short_circuits_without_llm_call(self):
        llm = _make_llm("should not be called")
        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="",
            llm=llm,
        )
        assert packet.company_catalysts == []
        assert packet.data_quality_notes
        llm.invoke.assert_not_called()

    def test_too_short_raw_news_short_circuits(self):
        llm = _make_llm("should not be called")
        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="hi",
            llm=llm,
        )
        assert packet.company_catalysts == []
        llm.invoke.assert_not_called()

    def test_unparseable_response_falls_back_to_empty_packet(self):
        llm = _make_llm("I refuse to output JSON, here's some prose instead.")
        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="x" * 200,
            llm=llm,
        )
        assert packet.company_catalysts == []
        assert any("JSON" in note for note in packet.data_quality_notes)

    def test_llm_exception_falls_back_to_empty_packet(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("network down")

        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="x" * 200,
            llm=llm,
        )
        assert packet.company_catalysts == []
        assert any("network down" in note for note in packet.data_quality_notes)

    def test_llm_returns_garbage_catalysts_drops_invalid_entries(self):
        response = """```json
{
  "company_catalysts": [
    {"title": "valid"},
    {"no_title": "x"},
    "not even a dict",
    {"title": "another valid", "type": "fundamental"}
  ],
  "macro_news": [],
  "noise_count": "not a number",
  "notes": []
}
```"""
        llm = _make_llm(response)
        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="x" * 200,
            llm=llm,
        )
        # Two valid catalysts kept, two invalid dropped
        titles = [c["title"] for c in packet.company_catalysts]
        assert "valid" in titles
        assert "another valid" in titles
        assert len(packet.company_catalysts) == 2
        # Invalid noise_count coerces to 0
        assert packet.noise_count == 0

    def test_caps_company_catalysts_at_six(self):
        items = [
            {
                "id": f"item_{i}",
                "type": "event",
                "title": f"Catalyst {i}",
                "expected_impact": "neutral",
                "confidence": "low",
                "sources": [],
            }
            for i in range(20)
        ]
        response = "```json\n" + json.dumps({
            "company_catalysts": items,
            "macro_news": [],
            "noise_count": 0,
            "notes": [],
        }) + "\n```"
        llm = _make_llm(response)
        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="x" * 200,
            llm=llm,
        )
        assert len(packet.company_catalysts) == 6

    def test_caps_macro_news_at_four(self):
        items = [{"title": f"macro {i}", "expected_effect": "x"} for i in range(10)]
        response = "```json\n" + json.dumps({
            "company_catalysts": [],
            "macro_news": items,
            "noise_count": 0,
            "notes": [],
        }) + "\n```"
        llm = _make_llm(response)
        packet = build_news_packet_from_text(
            instrument=SAMSUNG_INSTRUMENT,
            as_of="2026-04-10",
            raw_news_text="x" * 200,
            llm=llm,
        )
        assert len(packet.macro_news) == 4
