"""Tests for news noise filtering module."""

import unittest

from tradingagents.dataflows.news_filter import (
    is_spam,
    get_source_credibility,
    deduplicate_by_title,
    filter_news_text,
    SPAM_KEYWORDS,
    TRUSTED_SOURCES,
)


class TestIsSpam(unittest.TestCase):

    def test_detects_spam_keywords(self):
        self.assertTrue(is_spam("급등주 TOP 5 추천"))
        self.assertTrue(is_spam("무료 리딩 카톡방 안내"))
        self.assertTrue(is_spam("[광고] 주식 전문가 상담"))
        self.assertTrue(is_spam("VIP 종목 수익인증"))

    def test_normal_articles_not_spam(self):
        self.assertFalse(is_spam("삼성전자, 1분기 영업이익 15조원"))
        self.assertFalse(is_spam("한국은행 기준금리 동결 결정"))
        self.assertFalse(is_spam("코스피 2700선 돌파"))
        self.assertFalse(is_spam("SK하이닉스 HBM3E 양산 본격화"))

    def test_checks_description_too(self):
        self.assertTrue(is_spam("일반 제목", "무료추천 카카오톡 상담"))
        self.assertFalse(is_spam("일반 제목", "일반 설명"))


class TestSourceCredibility(unittest.TestCase):

    def test_trusted_sources(self):
        self.assertEqual(get_source_credibility("연합뉴스"), "high")
        self.assertEqual(get_source_credibility("한국경제"), "high")
        self.assertEqual(get_source_credibility("매일경제"), "high")
        self.assertEqual(get_source_credibility("이데일리"), "high")
        self.assertEqual(get_source_credibility("Bloomberg"), "high")

    def test_low_credibility(self):
        self.assertEqual(get_source_credibility("블로그"), "low")
        self.assertEqual(get_source_credibility("tistory.com"), "low")

    def test_medium_credibility(self):
        self.assertEqual(get_source_credibility("알 수 없는 매체"), "medium")

    def test_empty_source(self):
        self.assertEqual(get_source_credibility(""), "low")


class TestDeduplicateByTitle(unittest.TestCase):

    def test_removes_similar_titles(self):
        articles = [
            {"title": "삼성전자 1분기 영업이익 15조원 돌파"},
            {"title": "삼성전자 1분기 영업이익 15조원 기록"},  # very similar
            {"title": "SK하이닉스 HBM 수주 확대"},
        ]
        result = deduplicate_by_title(articles, threshold=0.75)
        self.assertEqual(len(result), 2)

    def test_keeps_different_articles(self):
        articles = [
            {"title": "삼성전자 실적 발표"},
            {"title": "현대차 전기차 판매 호조"},
            {"title": "한국은행 금리 동결"},
        ]
        result = deduplicate_by_title(articles, threshold=0.75)
        self.assertEqual(len(result), 3)

    def test_empty_list(self):
        self.assertEqual(deduplicate_by_title([]), [])

    def test_single_article(self):
        articles = [{"title": "test"}]
        self.assertEqual(len(deduplicate_by_title(articles)), 1)


class TestFilterNewsText(unittest.TestCase):

    def test_removes_spam_articles(self):
        text = """[1] 삼성전자 실적 호조
    Date: 2026-03-27
    Summary: 영업이익 증가

[2] 급등주 TOP 5 무료 리딩 추천
    Date: 2026-03-27
    Summary: 카톡방 참여하세요

[3] SK하이닉스 HBM 수주
    Date: 2026-03-27
    Summary: 대규모 계약"""

        result = filter_news_text(text)
        self.assertIn("삼성전자 실적 호조", result)
        self.assertIn("SK하이닉스 HBM 수주", result)
        self.assertNotIn("급등주 TOP 5", result)
        self.assertIn("1 low-quality/spam articles removed", result)

    def test_no_spam_no_change(self):
        text = "[1] 정상 기사\n    Summary: 정상 내용"
        result = filter_news_text(text)
        self.assertIn("정상 기사", result)
        self.assertNotIn("removed", result)

    def test_empty_text(self):
        self.assertEqual(filter_news_text(""), "")
        self.assertIsNone(filter_news_text(None))


if __name__ == "__main__":
    unittest.main()
