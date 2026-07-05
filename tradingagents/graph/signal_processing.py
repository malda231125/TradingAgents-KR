# TradingAgents/graph/signal_processing.py

import logging
import re

logger = logging.getLogger(__name__)


_CANONICAL = ("BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL")

# Korean → canonical English mapping. Both labels are accepted in the prompt
# templates so the parser must handle either spelling.
_KO_TO_EN = {
    "매수": "BUY",
    "비중확대": "OVERWEIGHT",
    "보유": "HOLD",
    "중립": "HOLD",
    "비중축소": "UNDERWEIGHT",
    "매도": "SELL",
}

# Match an explicit `Rating: <value>` (or markdown-bolded variant) anywhere in the text.
# This is the primary path because the Portfolio Manager prompt instructs the LLM
# to emit a Rating field.
_EXPLICIT_RATING_RE = re.compile(
    r"""
    (?:\*\*\s*)?Rating(?:\s*\*\*)?     # 'Rating' optionally wrapped in **bold**
    \s*[:\-]\s*                        # separator (: or -)
    (?:\*\*\s*)?                       # value may also be bolded
    (Buy|Overweight|Hold|Underweight|Sell|매수|비중확대|보유|중립|비중축소|매도)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Also support the Portfolio Manager's section-style markdown, e.g.:
# `**1. Rating**` on one line and `**Underweight**` on the next line.
_SECTION_RATING_RE = re.compile(
    r"""
    (?:\*\*\s*)?(?:\d+\.\s*)?Rating(?:\s*\*\*)?   # heading text
    \s*
    (?:\r?\n|\r)+                                # value on following line
    [>\-\*\s`_]*                                 # optional markdown/list adornment
    (?:\*\*\s*)?                                 # optional bold open
    (Buy|Overweight|Hold|Underweight|Sell|매수|비중확대|보유|중립|비중축소|매도)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Fallback: any standalone rating token in the text. Used only if no explicit
# 'Rating: X' line is present.
#
# Two patterns because regex `\b` does not work for Hangul (Korean characters
# are not classified as word characters by Python's `re` module). For English
# tokens we want word-boundary protection; for Korean tokens we accept the
# bare substring, which is acceptable since these tokens almost never appear
# inside unrelated compounds in trading text.
_FALLBACK_EN_RE = re.compile(
    r"\b(Buy|Overweight|Hold|Underweight|Sell)\b",
    re.IGNORECASE,
)
_FALLBACK_KO_RE = re.compile(
    r"(?<![가-힣A-Za-z])(매수|비중확대|보유|중립|비중축소|매도)(?:[이가은는을를의로와과만도]?)"
    r"(?![가-힣A-Za-z])",
)


def _normalize(token: str) -> str:
    """Normalize a raw matched token to one of the canonical English ratings."""
    if not token:
        return "HOLD"
    if token in _KO_TO_EN:
        return _KO_TO_EN[token]
    upper = token.upper()
    if upper in _CANONICAL:
        return upper
    return "HOLD"


def extract_rating(full_signal: str) -> str:
    """Deterministically extract the trading rating from a Portfolio Manager
    decision text.

    Resolution order:
    1. The last explicit `Rating: X` line (most authoritative — the prompt
       template requires this format).
    2. The last section-style `Rating` block where the value is on the next line.
    3. The last bare rating keyword anywhere in the text.
    4. `HOLD` as a safe default with a warning log.
    """
    text = full_signal or ""

    explicit = _EXPLICIT_RATING_RE.findall(text)
    if explicit:
        return _normalize(explicit[-1])

    section = _SECTION_RATING_RE.findall(text)
    if section:
        return _normalize(section[-1])

    # Collect all bare tokens from both patterns and pick the one that appears
    # latest in the document, regardless of script.
    bare_matches: list[tuple[int, str]] = []
    for m in _FALLBACK_EN_RE.finditer(text):
        bare_matches.append((m.start(), m.group(1)))
    for m in _FALLBACK_KO_RE.finditer(text):
        bare_matches.append((m.start(), m.group(1)))

    if bare_matches:
        bare_matches.sort(key=lambda pair: pair[0])
        return _normalize(bare_matches[-1][1])

    logger.warning(
        "SignalProcessor: no rating token found in final_trade_decision; defaulting to HOLD"
    )
    return "HOLD"


class SignalProcessor:
    """Extracts the canonical trading rating from a Portfolio Manager decision.

    Historically this was an LLM call that was instructed to output a single
    word. That call has been replaced by deterministic regex extraction:
    - The Portfolio Manager prompt already mandates a `Rating: X` line, so
      regex is functionally equivalent to the prior LLM extraction.
    - Removing the call eliminates one CLI subprocess invocation per run and
      its associated wall-clock cost / timeout risk.
    """

    def __init__(self, quick_thinking_llm=None):
        # Argument retained for backwards compatibility with TradingAgentsGraph,
        # which still constructs `SignalProcessor(self.quick_thinking_llm)`.
        self._llm = quick_thinking_llm

    def process_signal(self, full_signal: str) -> str:
        return extract_rating(full_signal)
