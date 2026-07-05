"""Report-language (i18n) resolution.

Single source of truth for the output language of agent responses, the news
enricher, the self-loop fallback checklist, and the Markdown report scaffolding.
The active language comes from ``report_language`` in the run config (set via
the ``TRADINGAGENTS_REPORT_LANGUAGE`` env var, default ``ko``).

Adding a language = add an entry to ``LANGUAGE_INSTRUCTIONS``, ``LANGUAGE_NAMES``,
``REPORT_STRINGS`` and ``DEFAULT_CHECKLIST``. Unknown codes fall back to English.
"""

from __future__ import annotations

from typing import Any

DEFAULT_LANGUAGE = "en"

# Appended to every agent system prompt to fix the OUTPUT language. We emit an
# explicit instruction for EVERY language, including English: the input context
# (KIS data, Korean company names, Naver news) is Korean-heavy, so without an
# explicit "respond in English" the model follows the data and answers in Korean.
LANGUAGE_INSTRUCTIONS = {
    "en": "\n\nIMPORTANT: Write your entire response in English.",
    "ko": "\n\nIMPORTANT: Write your entire response in Korean (한국어로 작성하세요).",
    "ja": "\n\nIMPORTANT: Write your entire response in Japanese (日本語で記述してください).",
    "zh": "\n\nIMPORTANT: Write your entire response in Chinese (请用简体中文撰写).",
}

# Human-readable language name for prompts that must name the target language
# (e.g. the news enricher: "write all titles in {name}").
LANGUAGE_NAMES = {
    "en": "English",
    "ko": "Korean (한국어)",
    "ja": "Japanese (日本語)",
    "zh": "Simplified Chinese (简体中文)",
}

SUPPORTED_LANGUAGES = tuple(LANGUAGE_INSTRUCTIONS.keys())

# Localized strings for the Markdown report scaffolding (section headers,
# metadata labels). Body content is produced by the agents in the target
# language; these keep the scaffolding consistent with it.
REPORT_STRINGS = {
    "en": {
        "run_title": "TradingAgents Run",
        "exported_at": "Exported at",
        "kv_item": "Field", "kv_value": "Value", "total": "Total",
        "run_metadata": "Run metadata",
        "ticker": "Ticker", "trade_date": "Trade date", "final_signal": "Final signal",
        "wall_clock": "Wall-clock", "cli_calls": "CLI calls",
        "sl_context": "Self-loop retrospective context",
        "sl_result": "Self-loop retrospective result",
        "sl_prior_date": "Prior analysis date", "sl_prior_decision": "Prior decision",
        "sl_outcome": "Outcome", "sl_lesson": "Lesson",
        "market": "Market analyst report", "news": "News analyst report",
        "fundamentals": "Fundamentals analyst report",
        "debate": "Bull/Bear debate history", "rm_decision": "Research Manager decision",
        "investment_plan": "Investment plan (Research Manager)", "trader_plan": "Trader plan",
        "risk_debate": "Risk debate history",
        "final_decision": "Final trade decision (Portfolio Manager)",
    },
    "ko": {
        "run_title": "TradingAgents 실행",
        "exported_at": "내보낸 시각",
        "kv_item": "항목", "kv_value": "값", "total": "합계",
        "run_metadata": "실행 메타데이터",
        "ticker": "종목", "trade_date": "분석일", "final_signal": "최종 시그널",
        "wall_clock": "소요 시간", "cli_calls": "CLI 호출 수",
        "sl_context": "Self-loop 회고 컨텍스트",
        "sl_result": "Self-loop 회고 결과",
        "sl_prior_date": "직전 분석일", "sl_prior_decision": "직전 결정",
        "sl_outcome": "결과", "sl_lesson": "교훈",
        "market": "마켓 애널리스트 리포트", "news": "뉴스 애널리스트 리포트",
        "fundamentals": "펀더멘털 애널리스트 리포트",
        "debate": "불/베어 토론 내역", "rm_decision": "리서치 매니저 결정",
        "investment_plan": "투자 플랜 (리서치 매니저)", "trader_plan": "트레이더 플랜",
        "risk_debate": "리스크 토론 내역",
        "final_decision": "최종 매매 결정 (포트폴리오 매니저)",
    },
    "ja": {
        "run_title": "TradingAgents 実行",
        "exported_at": "エクスポート日時",
        "kv_item": "項目", "kv_value": "値", "total": "合計",
        "run_metadata": "実行メタデータ",
        "ticker": "銘柄", "trade_date": "分析日", "final_signal": "最終シグナル",
        "wall_clock": "所要時間", "cli_calls": "CLI 呼び出し数",
        "sl_context": "Self-loop レトロスペクティブ・コンテキスト",
        "sl_result": "Self-loop レトロスペクティブ結果",
        "sl_prior_date": "前回分析日", "sl_prior_decision": "前回の判断",
        "sl_outcome": "結果", "sl_lesson": "教訓",
        "market": "マーケットアナリスト・レポート", "news": "ニュースアナリスト・レポート",
        "fundamentals": "ファンダメンタルズアナリスト・レポート",
        "debate": "強気/弱気ディベート履歴", "rm_decision": "リサーチマネージャーの判断",
        "investment_plan": "投資プラン（リサーチマネージャー）", "trader_plan": "トレーダープラン",
        "risk_debate": "リスクディベート履歴",
        "final_decision": "最終売買判断（ポートフォリオマネージャー）",
    },
    "zh": {
        "run_title": "TradingAgents 运行",
        "exported_at": "导出时间",
        "kv_item": "项目", "kv_value": "值", "total": "合计",
        "run_metadata": "运行元数据",
        "ticker": "标的", "trade_date": "分析日", "final_signal": "最终信号",
        "wall_clock": "耗时", "cli_calls": "CLI 调用次数",
        "sl_context": "Self-loop 复盘上下文",
        "sl_result": "Self-loop 复盘结果",
        "sl_prior_date": "上次分析日", "sl_prior_decision": "上次决策",
        "sl_outcome": "结果", "sl_lesson": "经验",
        "market": "市场分析师报告", "news": "新闻分析师报告",
        "fundamentals": "基本面分析师报告",
        "debate": "多空辩论记录", "rm_decision": "研究经理决策",
        "investment_plan": "投资计划（研究经理）", "trader_plan": "交易员计划",
        "risk_debate": "风险辩论记录",
        "final_decision": "最终交易决策（投资组合经理）",
    },
}

# Fallback prediction checklist for the self-loop decision record (used only
# when AI extraction fails). Must include an explicit price-direction check.
DEFAULT_CHECKLIST = {
    "en": [
        "Does the closing-price return over the review horizon match the decision direction?",
        "Did none of the key risk triggers fire?",
        "Did the news / disclosure / macro environment leave the original thesis intact?",
    ],
    "ko": [
        "review horizon 내 종가 수익률이 decision 방향과 일치하는가?",
        "주요 risk trigger가 발생하지 않았는가?",
        "뉴스/공시/매크로 환경이 기존 thesis를 훼손하지 않았는가?",
    ],
    "ja": [
        "レビュー期間中の終値リターンは判断の方向と一致しているか？",
        "主要なリスクトリガーは発生しなかったか？",
        "ニュース・開示・マクロ環境は当初のテーゼを損なっていないか？",
    ],
    "zh": [
        "复盘期间的收盘价收益方向是否与决策一致？",
        "主要风险触发条件是否均未发生？",
        "新闻/披露/宏观环境是否未损害原有逻辑？",
    ],
}


def normalize_language(lang: Any) -> str:
    """Normalize a language value to a supported code, falling back to English.

    Accepts ``ko``, ``KO``, ``ko-KR``, ``en_US`` etc.; unknown codes → ``en``.
    """
    code = str(lang or "").strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGUAGE_INSTRUCTIONS else DEFAULT_LANGUAGE


def resolve_report_language(config: dict | None = None) -> str:
    """Resolve the active report language code from config (or the global config)."""
    if config is None:
        from tradingagents.dataflows.config import get_config

        config = get_config()
    return normalize_language((config or {}).get("report_language"))


def get_language_instruction(config: dict | None = None) -> str:
    """Prompt suffix that fixes the agent output language.

    Non-empty for every supported language, English included: the input context
    is Korean-heavy, so English must be stated explicitly or the model drifts.
    """
    return LANGUAGE_INSTRUCTIONS[resolve_report_language(config)]


def get_output_language_name(config: dict | None = None) -> str:
    """Human-readable name of the active output language (for naming it in prompts)."""
    return LANGUAGE_NAMES[resolve_report_language(config)]


def get_report_strings(lang: Any = None) -> dict:
    """Localized Markdown-scaffolding strings for the given/active language."""
    code = normalize_language(lang) if lang is not None else resolve_report_language()
    return REPORT_STRINGS[code]


def get_default_prediction_checklist(config: dict | None = None) -> list[str]:
    """Language-aware fallback prediction checklist for self-loop decision records."""
    return list(DEFAULT_CHECKLIST[resolve_report_language(config)])
