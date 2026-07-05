"""DART disclosure event classifier for Korean market analysis.

Auto-classifies DART disclosure titles by:
1. Event type (earnings, capital change, governance, etc.)
2. Market impact (positive, negative, neutral, needs_review)

This helps the analyst quickly identify which disclosures matter
for trading decisions.
"""

from typing import Tuple

# Event classification rules: (keyword_list, event_type, default_impact)
EVENT_RULES = [
    # === Positive signals ===
    (["자기주식 취득", "자사주 취득", "자기주식취득"],
     "자사주 매입", "positive"),
    (["배당", "현금배당", "주당배당"],
     "배당", "positive"),
    (["대규모 수주", "공급계약", "납품계약", "수주공시"],
     "대규모 수주/계약", "positive"),
    (["자기주식 소각", "자사주 소각"],
     "자사주 소각", "positive"),
    (["신규시설투자", "시설투자"],
     "설비 투자", "positive"),
    (["전환사채 조기상환", "CB 조기상환"],
     "CB 조기상환", "positive"),

    # === Negative signals ===
    (["유상증자"],
     "유상증자", "negative"),
    (["감자", "무상감자", "유상감자"],
     "감자", "negative"),
    (["횡령", "배임"],
     "횡령/배임", "negative"),
    (["상장폐지", "관리종목"],
     "상장폐지/관리종목", "negative"),
    (["영업정지", "사업중단"],
     "영업정지", "negative"),
    (["소송", "피소"],
     "소송", "negative"),
    (["전환사채 발행", "CB 발행", "신주인수권부사채"],
     "CB/BW 발행", "negative"),
    (["주식관련사채권 행사", "전환권 행사"],
     "전환권 행사 (희석)", "negative"),

    # === Neutral / needs context ===
    (["사업보고서", "분기보고서", "반기보고서"],
     "정기 보고서", "neutral"),
    (["기재정정"],
     "기재 정정", "neutral"),
    (["임원", "대표이사", "이사회"],
     "임원/이사회 변동", "needs_review"),
    (["최대주주", "주요주주", "지분변동"],
     "주요주주 변동", "needs_review"),
    (["합병", "분할"],
     "합병/분할", "needs_review"),
    (["정관", "주주총회"],
     "정관/주주총회", "neutral"),
    (["타법인주식", "출자"],
     "타법인 투자", "needs_review"),
    (["실적", "매출액", "영업이익"],
     "실적 공시", "needs_review"),
    (["공개매수"],
     "공개매수", "needs_review"),
    (["무상증자"],
     "무상증자", "positive"),
    (["주식배당"],
     "주식배당", "neutral"),
]

# Impact display markers
IMPACT_MARKERS = {
    "positive": "[+]",
    "negative": "[-]",
    "neutral": "[=]",
    "needs_review": "[?]",
    "unknown": "[·]",
}


def classify_disclosure(title: str) -> Tuple[str, str]:
    """Classify a DART disclosure title.

    Args:
        title: Disclosure report title (e.g. "유상증자결정", "사업보고서 (2025.12)")

    Returns:
        Tuple of (event_type, impact)
        event_type: Human-readable classification
        impact: "positive", "negative", "neutral", "needs_review", or "unknown"
    """
    title_lower = title.lower().replace(" ", "")

    for keywords, event_type, impact in EVENT_RULES:
        for keyword in keywords:
            if keyword.replace(" ", "") in title_lower:
                return event_type, impact

    return "기타 공시", "unknown"


def format_classified_disclosures(disclosures: list) -> str:
    """Format a list of DART disclosures with classification and impact labels.

    Args:
        disclosures: List of disclosure dicts with "report_nm", "rcept_dt", "flr_nm", etc.

    Returns:
        Formatted string with impact markers
    """
    if not disclosures:
        return "No disclosures to classify."

    lines = ["=== DART Disclosures (Classified) ===\n"]

    # Separate by impact for organized output
    by_impact = {"positive": [], "negative": [], "needs_review": [], "neutral": [], "unknown": []}

    for item in disclosures:
        title = item.get("report_nm", "")
        date = item.get("rcept_dt", "")
        filer = item.get("flr_nm", "")

        event_type, impact = classify_disclosure(title)
        marker = IMPACT_MARKERS.get(impact, "[·]")

        entry = f"  {marker} [{date}] {title} ({event_type})"
        if filer:
            entry += f" — {filer}"

        by_impact.get(impact, by_impact["unknown"]).append(entry)

    # Output negative first (most urgent), then needs_review, positive, neutral, unknown
    order = ["negative", "needs_review", "positive", "neutral", "unknown"]
    section_labels = {
        "negative": "주의 필요 (부정적 신호)",
        "needs_review": "확인 필요 (맥락에 따라 다름)",
        "positive": "긍정적 신호",
        "neutral": "일반/중립",
        "unknown": "미분류",
    }

    for impact in order:
        entries = by_impact[impact]
        if entries:
            lines.append(f"--- {section_labels[impact]} ---")
            lines.extend(entries)
            lines.append("")

    # Summary
    total = len(disclosures)
    neg = len(by_impact["negative"])
    pos = len(by_impact["positive"])
    review = len(by_impact["needs_review"])

    lines.append(f"[Summary: {total} disclosures — {neg} negative, {pos} positive, {review} needs review]")

    return "\n".join(lines)
