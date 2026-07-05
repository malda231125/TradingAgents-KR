"""News quality filtering for Korean financial news.

Filters out low-quality, spam, and duplicate articles before
passing news data to the News Analyst.
"""

import re
from difflib import SequenceMatcher
from typing import List, Tuple

# Spam/advertising keywords commonly found in low-quality Korean stock articles
SPAM_KEYWORDS = [
    "급등주", "테마주 추천", "무료 리딩", "무료추천", "수익인증",
    "VIP 종목", "특징주 포착", "찐 수익", "매수 타점",
    "오늘의 급등", "내일의 상한가", "비밀 종목", "폭등 예고",
    "카톡방", "카카오톡 상담", "텔레그램 채널",
    "주식리딩방", "리딩방 추천", "무료체험",
    "[광고]", "[AD]", "협찬", "제휴",
    "대박 종목", "100% 수익", "원금보장",
]

# Trusted news sources (higher credibility)
TRUSTED_SOURCES = {
    "연합뉴스", "연합인포맥스", "한국경제", "매일경제", "서울경제",
    "조선비즈", "한경비즈니스", "이데일리", "머니투데이", "뉴스1",
    "헤럴드경제", "아시아경제", "파이낸셜뉴스", "전자신문",
    "블룸버그", "로이터", "Reuters", "Bloomberg",
    "the bell", "더벨", "인포스탁", "한국거래소",
}

# Low credibility patterns (blog, community, unknown)
LOW_CREDIBILITY_PATTERNS = [
    r"블로그", r"카페", r"tistory", r"naver\.blog",
    r"뉴스핌.*\[광고\]", r"스팸", r"홍보",
]


def is_spam(title: str, description: str = "") -> bool:
    """Check if an article is likely spam/advertising.

    Args:
        title: Article title
        description: Article description/summary

    Returns:
        True if the article looks like spam
    """
    combined = (title + " " + description).lower()

    for keyword in SPAM_KEYWORDS:
        if keyword.lower() in combined:
            return True

    return False


def get_source_credibility(source: str) -> str:
    """Rate the credibility of a news source.

    Returns:
        "high", "medium", or "low"
    """
    if not source:
        return "low"

    for trusted in TRUSTED_SOURCES:
        if trusted.lower() in source.lower():
            return "high"

    for pattern in LOW_CREDIBILITY_PATTERNS:
        if re.search(pattern, source, re.IGNORECASE):
            return "low"

    return "medium"


def deduplicate_by_title(articles: List[dict], threshold: float = 0.75) -> List[dict]:
    """Remove duplicate articles based on title similarity.

    Uses SequenceMatcher to find articles with similar titles
    and keeps only the first occurrence (or the one from a more credible source).

    Args:
        articles: List of article dicts with at least "title" key
        threshold: Similarity threshold (0-1). Default 0.75 = 75% similar

    Returns:
        Deduplicated list of articles
    """
    if not articles:
        return articles

    kept = []
    kept_titles = []

    for article in articles:
        title = article.get("title", "")
        is_dup = False

        for existing_title in kept_titles:
            similarity = SequenceMatcher(None, title, existing_title).ratio()
            if similarity >= threshold:
                is_dup = True
                break

        if not is_dup:
            kept.append(article)
            kept_titles.append(title)

    return kept


def filter_news_text(news_text: str) -> str:
    """Filter a block of news text by removing spam lines and marking credibility.

    Parses the formatted news output (from naver_news.py etc.) and filters
    individual articles. This is a best-effort text-level filter.

    Args:
        news_text: Formatted news text with numbered articles

    Returns:
        Filtered text with spam removed and credibility markers added
    """
    if not news_text:
        return news_text

    lines = news_text.split("\n")
    filtered_lines = []
    skip_until_next_article = False
    current_title = ""
    articles_removed = 0

    for line in lines:
        # Detect article boundaries (numbered entries like "[1] Title")
        article_match = re.match(r"\[(\d+)\]\s*(.*)", line)

        if article_match:
            current_title = article_match.group(2)
            skip_until_next_article = False

            if is_spam(current_title):
                skip_until_next_article = True
                articles_removed += 1
                continue

        if skip_until_next_article:
            # Skip all lines belonging to this spam article
            if line.strip() == "" or line.startswith("    "):
                continue
            # Non-indented, non-empty line = next section/article
            skip_until_next_article = False

        filtered_lines.append(line)

    result = "\n".join(filtered_lines)

    if articles_removed > 0:
        result += f"\n\n[Filter note: {articles_removed} low-quality/spam articles removed]"

    return result
