"""News feature packet — NLU-driven extraction of structured catalysts.

Unlike the market and fundamentals packets which are 100% rule-based, the
news packet is built by a small LLM call that performs natural-language
understanding on the raw articles. This is the key insight from the
context-compression discussion: trying to extract event semantics with
rules ("expected_impact", "is this a real catalyst or just chatter?")
produces brittle output, but a focused single LLM call can do it well
once and the result is then reusable by downstream nodes.

Cost shape:

  - One enricher call per (ticker, trade_date), input ~10k chars,
    output ~1k chars of structured JSON.
  - The news_analyst then receives the structured packet (~1.5k chars
    when serialized) instead of the original 10k+ char text dump.
  - Result is cached on disk keyed by (ticker, date, hash(raw_news)),
    so re-runs of the same date are free.

Schema (returned as JSON by the enricher LLM):

  {
    "company_catalysts": [
      {
        "id": "...",                 // short slug
        "type": "event|fundamental|policy|regulatory|product|flow",
        "title": "...",              // human-readable headline
        "summary": "...",            // 1-2 sentence interpretation
        "expected_impact": "short_term_positive|short_term_negative|"
                           "medium_term_positive|medium_term_negative|"
                           "neutral",
        "confidence": "low|medium|high",
        "sources": ["naver", "yfinance"]
      }
    ],
    "macro_news": [
      {"title": "...", "expected_effect": "..."}
    ],
    "noise_count": 8,
    "notes": ["..."]
  }
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------


@dataclass
class NewsCatalyst:
    id: str
    type: str
    title: str
    summary: str
    expected_impact: str
    confidence: str
    sources: list[str]


@dataclass
class NewsPacket:
    instrument: dict
    as_of: str
    company_catalysts: list[dict]
    macro_news: list[dict]
    noise_count: int
    global_peer_events: list[dict] = field(default_factory=list)
    data_quality_notes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        return (
            "```json\n"
            + json.dumps(asdict(self), ensure_ascii=False, indent=2)
            + "\n```"
        )


# ----------------------------------------------------------------------
# Allowed schema values — used to normalize LLM output
# ----------------------------------------------------------------------


_ALLOWED_TYPES = {
    "event",
    "fundamental",
    "policy",
    "regulatory",
    "product",
    "flow",
}
_ALLOWED_IMPACTS = {
    "short_term_positive",
    "short_term_negative",
    "medium_term_positive",
    "medium_term_negative",
    "neutral",
}
_ALLOWED_CONFIDENCE = {"low", "medium", "high"}


# ----------------------------------------------------------------------
# Prompt construction
# ----------------------------------------------------------------------


_EXTRACTION_INSTRUCTIONS = """\
You are a news enrichment service for a Korean equity trading system.

Your job is NOT to write a report. Your job is to read the raw news text
below and produce a single, strict JSON object that catalogs the catalysts
that actually matter for trading the named instrument.

Rules:
- Output ONLY a single JSON object inside one fenced ```json``` block. No
  prose before or after the block.
- Consolidate articles that cover the same event into one catalyst entry.
  Set `sources` to the list of vendor names (naver, yfinance, etc.) that
  reported it.
- Skip pure noise (price-watching, generic market color, repeats with
  identical wording, low-quality clickbait). Count them in `noise_count`.
- For each catalyst, classify `type` as one of:
    event       - one-time corporate event (M&A, block deal, lawsuit, etc.)
    fundamental - earnings, guidance, margin, financial structure
    policy      - government / regulator action that moves a sector
    regulatory  - company-specific regulatory or compliance issue
    product     - new product, contract, supply / customer news
    flow        - foreign / institutional flow, short interest, ownership
- For each catalyst, classify `expected_impact` as one of:
    short_term_positive   - likely to push the stock up over days
    short_term_negative   - likely to push the stock down over days
    medium_term_positive  - structural improvement over weeks/months
    medium_term_negative  - structural deterioration over weeks/months
    neutral               - reported but unlikely to move the price
- For each catalyst, set `confidence` to low / medium / high based on
  source quality, article count, and how concrete the wording is.
- Include up to 6 company catalysts. Pick the most price-relevant ones.
- For `macro_news`, include up to 4 items that materially affect Korean
  equities (rates, FX, China demand, semiconductor cycle, foreign flow).
  Skip generic global news that does not flow back to KR markets.
- `notes` should list any data-quality caveats (one source only, vague
  wording, conflicting reports, etc.).

The JSON schema you MUST follow exactly:

```json
{
  "company_catalysts": [
    {
      "id": "short_slug",
      "type": "event|fundamental|policy|regulatory|product|flow",
      "title": "human readable headline",
      "summary": "1-2 sentence trading-relevant interpretation",
      "expected_impact": "short_term_positive|short_term_negative|medium_term_positive|medium_term_negative|neutral",
      "confidence": "low|medium|high",
      "sources": ["naver", "yfinance"]
    }
  ],
  "macro_news": [
    {"title": "...", "expected_effect": "..."}
  ],
  "noise_count": 0,
  "notes": []
}
```

If there are no real catalysts, return an empty `company_catalysts` list
and explain in `notes`.
"""


def _build_extraction_prompt(
    instrument: dict, as_of: str, raw_news_text: str
) -> str:
    from tradingagents.i18n import get_output_language_name

    name = instrument.get("name") or ""
    stock_code = instrument.get("stock_code") or ""
    language_directive = (
        "Write all human-readable text (every `title`, `summary`, `notes` and "
        f"`expected_effect` value) in {get_output_language_name()}. Keep enum "
        "fields (`type`, `expected_impact`, `confidence`) and `id`/`sources` as "
        "the literal ASCII tokens defined in the schema."
    )
    return (
        _EXTRACTION_INSTRUCTIONS
        + "\n\n"
        + language_directive
        + f"\n\nInstrument: {name} ({stock_code})\n"
        + f"As of: {as_of}\n\n"
        + "--- RAW NEWS TEXT ---\n\n"
        + raw_news_text
    )


# ----------------------------------------------------------------------
# Response parsing
# ----------------------------------------------------------------------


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_object(text: str) -> Optional[dict]:
    """Pull the first JSON object out of an LLM response.

    Tries fenced blocks first, then falls back to scanning for a balanced
    `{...}` substring. Returns None if nothing parses.
    """
    if not text:
        return None

    fenced = _JSON_BLOCK_RE.search(text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: find the first balanced top-level object
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = -1
                    continue
    return None


def _normalize_catalyst(raw: dict) -> Optional[dict]:
    """Validate and normalize a single catalyst dict from the LLM output."""
    if not isinstance(raw, dict):
        return None

    title = str(raw.get("title", "")).strip()
    if not title:
        return None

    type_value = str(raw.get("type", "")).strip().lower()
    if type_value not in _ALLOWED_TYPES:
        type_value = "event"

    impact = str(raw.get("expected_impact", "")).strip().lower()
    if impact not in _ALLOWED_IMPACTS:
        impact = "neutral"

    confidence = str(raw.get("confidence", "")).strip().lower()
    if confidence not in _ALLOWED_CONFIDENCE:
        confidence = "medium"

    sources_raw = raw.get("sources") or []
    if not isinstance(sources_raw, list):
        sources_raw = [str(sources_raw)]
    sources = [str(s).strip().lower() for s in sources_raw if str(s).strip()]

    return {
        "id": str(raw.get("id", "")).strip() or _slugify(title),
        "type": type_value,
        "title": title,
        "summary": str(raw.get("summary", "")).strip(),
        "expected_impact": impact,
        "confidence": confidence,
        "sources": sources,
    }


def _slugify(text: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^\w가-힣]+", "_", text.lower()).strip("_")
    return cleaned[:max_len] or "catalyst"


def _normalize_macro_item(raw: Any) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title", "")).strip()
    if not title:
        return None
    return {
        "title": title,
        "expected_effect": str(raw.get("expected_effect", "")).strip(),
    }


def _parse_response(
    response_text: str,
    *,
    instrument: dict,
    as_of: str,
    evidence_refs: list[str],
) -> NewsPacket:
    parsed = _extract_json_object(response_text)
    if parsed is None:
        logger.warning("News enricher returned unparseable response; falling back to empty packet")
        return NewsPacket(
            instrument=instrument,
            as_of=as_of,
            company_catalysts=[],
            macro_news=[],
            noise_count=0,
            data_quality_notes=["enricher 응답에서 JSON을 추출하지 못함 — fallback 빈 패킷"],
            evidence_refs=evidence_refs,
        )

    raw_catalysts = parsed.get("company_catalysts") or []
    if not isinstance(raw_catalysts, list):
        raw_catalysts = []
    catalysts = []
    for item in raw_catalysts:
        normalized = _normalize_catalyst(item)
        if normalized is not None:
            catalysts.append(normalized)
    catalysts = catalysts[:6]

    raw_macro = parsed.get("macro_news") or []
    if not isinstance(raw_macro, list):
        raw_macro = []
    macro_items = []
    for item in raw_macro:
        normalized = _normalize_macro_item(item)
        if normalized is not None:
            macro_items.append(normalized)
    macro_items = macro_items[:4]

    noise_count = parsed.get("noise_count", 0)
    try:
        noise_count = int(noise_count)
    except (TypeError, ValueError):
        noise_count = 0

    notes = parsed.get("notes") or []
    if not isinstance(notes, list):
        notes = [str(notes)]
    notes = [str(n).strip() for n in notes if str(n).strip()]

    return NewsPacket(
        instrument=instrument,
        as_of=as_of,
        company_catalysts=catalysts,
        macro_news=macro_items,
        noise_count=noise_count,
        data_quality_notes=notes,
        evidence_refs=evidence_refs,
    )


# ----------------------------------------------------------------------
# Builder API
# ----------------------------------------------------------------------


def build_news_packet_from_text(
    *,
    instrument: dict,
    as_of: str,
    raw_news_text: str,
    llm: Any,
    evidence_refs: Optional[list[str]] = None,
) -> NewsPacket:
    """Run the NLU enricher on a raw news text blob and return a NewsPacket.

    `llm` must implement LangChain's `BaseChatModel.invoke()` interface.
    Failures (LLM error, malformed JSON, empty input) all degrade to a
    well-formed empty packet so the analyst graph never crashes.
    """
    refs = evidence_refs or []

    if not raw_news_text or len(raw_news_text.strip()) < 50:
        return NewsPacket(
            instrument=instrument,
            as_of=as_of,
            company_catalysts=[],
            macro_news=[],
            noise_count=0,
            data_quality_notes=["raw news 데이터가 너무 짧거나 비어 있음"],
            evidence_refs=refs,
        )

    prompt = _build_extraction_prompt(instrument, as_of, raw_news_text)

    try:
        response = llm.invoke(prompt)
    except Exception as exc:
        logger.warning("News enricher LLM call failed: %s", exc)
        return NewsPacket(
            instrument=instrument,
            as_of=as_of,
            company_catalysts=[],
            macro_news=[],
            noise_count=0,
            data_quality_notes=[f"enricher 호출 실패: {exc}"],
            evidence_refs=refs,
        )

    response_text = getattr(response, "content", None) or str(response)
    return _parse_response(
        response_text,
        instrument=instrument,
        as_of=as_of,
        evidence_refs=refs,
    )


def build_news_packet(ticker: str, trade_date: str, llm: Any) -> NewsPacket:
    """Live convenience builder. Resolves the ticker, fetches the merged
    raw news text via the existing prefetch path, then runs the enricher.
    """
    from tradingagents.dataflows.korea_ticker import get_instrument_profile
    from tradingagents.dataflows.prefetch import prefetch_news_data

    profile = get_instrument_profile(ticker)
    instrument = {
        "name": profile.get("name") or ticker,
        "stock_code": profile.get("stock_code") or ticker,
    }

    try:
        raw = prefetch_news_data(ticker, trade_date)
    except Exception as exc:
        logger.warning("prefetch_news_data failed for %s: %s", ticker, exc)
        raw = ""

    return build_news_packet_from_text(
        instrument=instrument,
        as_of=trade_date,
        raw_news_text=raw,
        llm=llm,
        evidence_refs=[f"news:raw:{ticker}:{trade_date}"],
    )
