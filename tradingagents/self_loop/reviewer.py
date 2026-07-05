from __future__ import annotations

import json
import re
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import create_llm_client


VALID_OUTCOMES = {"hit", "miss", "partial", "uncertain"}
VALID_DECISIONS = {"buy_review", "sell_review", "hold", "watch"}
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_TRIGGER_STATUSES = {"fired", "not_fired", "uncertain"}


def _build_subscription_llm(config: dict[str, Any] | None = None):
    cfg = (config or DEFAULT_CONFIG).copy()
    return create_llm_client(
        provider=cfg.get("llm_provider"),
        model=cfg.get("quick_think_llm"),
        base_url=cfg.get("backend_url"),
        timeout=cfg.get("cli_timeout", 300),
        max_retries=cfg.get("cli_max_retries", 2),
    ).get_llm()


def extract_decision_with_ai(
    final_state: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Infer the structured decision record fields from analyst output via the LLM.

    This replaces keyword/regex extraction: the model reads the investment plan,
    trader plan, and final decision text and reasons about meaning. Returns a
    dict with ``decision``, ``confidence``, ``thesis``, ``key_risk_triggers``,
    and ``prediction_checklist``. Raises on transport/parse failure so callers
    can fall back deterministically.
    """
    llm = _build_subscription_llm(config)
    response = llm.invoke(build_decision_extraction_prompt(final_state))
    content = getattr(response, "content", response)
    return parse_decision_extraction_response(str(content))


def build_decision_extraction_prompt(final_state: dict[str, Any]) -> str:
    evidence = {
        "investment_plan": str(final_state.get("investment_plan") or ""),
        "trader_investment_plan": str(final_state.get("trader_investment_plan") or ""),
        "final_trade_decision": str(final_state.get("final_trade_decision") or ""),
    }
    return (
        "You are extracting a structured decision record from a Korean equity research run.\n"
        "Read the analyst plans and the final decision, then reason about their MEANING. "
        "Do not rely on keyword matching; infer intent even when phrased indirectly.\n"
        "Classify the action:\n"
        "- buy_review: net bullish / accumulate / add / open long bias\n"
        "- sell_review: net bearish / reduce / trim / open short bias\n"
        "- hold: keep current exposure, no change\n"
        "- watch: no actionable edge yet, monitor only\n"
        "Return strict JSON only with this schema:\n"
        "{\n"
        '  "decision": "buy_review|sell_review|hold|watch",\n'
        '  "confidence": "low|medium|high",\n'
        '  "thesis": "1-2 sentence core thesis",\n'
        '  "key_risk_triggers": ["conditions that would invalidate the thesis"],\n'
        '  "prediction_checklist": ["falsifiable checks to score after the review horizon; '
        'include at least one explicit price-direction check"]\n'
        "}\n\n"
        "Evidence JSON:\n"
        f"{json.dumps(evidence, ensure_ascii=False, indent=2)}"
    )


def parse_decision_extraction_response(text: str) -> dict[str, Any]:
    payload = _extract_json(text)
    decision = str(payload.get("decision", "")).strip().lower()
    confidence = str(payload.get("confidence", "medium")).strip().lower()
    if confidence not in VALID_CONFIDENCE:
        confidence = "medium"
    return {
        "decision": decision,
        "confidence": confidence,
        "thesis": str(payload.get("thesis") or "").strip(),
        "key_risk_triggers": _as_str_list(payload.get("key_risk_triggers")),
        "prediction_checklist": _as_str_list(payload.get("prediction_checklist")),
    }


def _as_str_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = " ".join(str(item).split())
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def review_with_subscription_ai(
    decision_record: dict[str, Any],
    preliminary: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = (config or DEFAULT_CONFIG).copy()
    provider = cfg.get("llm_provider")
    model = cfg.get("quick_think_llm")
    llm = create_llm_client(
        provider=provider,
        model=model,
        base_url=cfg.get("backend_url"),
        timeout=cfg.get("cli_timeout", 300),
        max_retries=cfg.get("cli_max_retries", 2),
    ).get_llm()
    response = llm.invoke(build_review_prompt(decision_record, preliminary))
    content = getattr(response, "content", response)
    return parse_review_response(str(content))


def detect_key_risk_trigger_with_subscription_ai(
    decision_record: dict[str, Any],
    evidence_packet: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Judge whether any prior Key Risk Trigger fired before review_due.

    Daily trigger checks are not final retrospectives. They answer a narrower
    question: did today's evidence hit one of the prior trigger conditions?
    The self-loop review is run separately only when this returns ``fired``.
    """
    cfg = (config or DEFAULT_CONFIG).copy()
    provider = cfg.get("llm_provider")
    model = cfg.get("quick_think_llm")
    llm = create_llm_client(
        provider=provider,
        model=model,
        base_url=cfg.get("backend_url"),
        timeout=cfg.get("cli_timeout", 300),
        max_retries=cfg.get("cli_max_retries", 2),
    ).get_llm()
    response = llm.invoke(build_trigger_detection_prompt(decision_record, evidence_packet))
    content = getattr(response, "content", response)
    return parse_trigger_detection_response(str(content))


def summarize_lessons_with_subscription_ai(
    *,
    ticker: str,
    lessons: list[dict[str, Any]],
    previous_summary: str = "",
    config: dict[str, Any] | None = None,
) -> str:
    cfg = (config or DEFAULT_CONFIG).copy()
    provider = cfg.get("llm_provider")
    model = cfg.get("quick_think_llm")
    llm = create_llm_client(
        provider=provider,
        model=model,
        base_url=cfg.get("backend_url"),
        timeout=cfg.get("cli_timeout", 300),
        max_retries=cfg.get("cli_max_retries", 2),
    ).get_llm()
    prompt = build_lesson_summary_prompt(
        ticker=ticker,
        lessons=lessons,
        previous_summary=previous_summary,
    )
    response = llm.invoke(prompt)
    content = getattr(response, "content", response)
    summary = str(content).strip()
    return summary or deterministic_lesson_summary(ticker=ticker, lessons=lessons)


def deterministic_lesson_summary(*, ticker: str, lessons: list[dict[str, Any]]) -> str:
    recent = [str(item.get("lesson") or "").strip() for item in lessons if item.get("lesson")]
    recent = recent[-10:]
    lines = [f"# Self-loop lesson summary — {ticker}", ""]
    if not recent:
        lines.append("No lessons recorded yet.")
    else:
        lines.append("Recent recurring lessons:")
        for lesson in recent:
            lines.append(f"- {lesson}")
    return "\n".join(lines)


def build_review_prompt(
    decision_record: dict[str, Any],
    preliminary: dict[str, Any],
) -> str:
    evidence = {
        "decision_record": decision_record,
        "preliminary_retrospective": preliminary,
    }
    return (
        "You are reviewing a Korean equity research prediction after the fact.\n"
        "Use the evidence only. Do not invent market data. If evidence for a "
        "checklist item is missing (see preliminary_retrospective.evidence and "
        "missing_evidence), score that item uncertain rather than guessing.\n"
        "Judge EACH prediction_checklist item, then the overall thesis "
        "(hit, miss, partial, or uncertain).\n"
        "Return strict JSON only with this schema:\n"
        "{\n"
        '  "overall": "hit|miss|partial|uncertain",\n'
        '  "reasoning": "short evidence-based rationale",\n'
        '  "checklist_results": [\n'
        '    {"item": "checklist item text", "status": "hit|miss|partial|uncertain", "reason": "evidence-based"}\n'
        "  ],\n"
        '  "lesson": "specific lesson for the next analysis, or null if no lesson",\n'
        '  "confidence": "low|medium|high"\n'
        "}\n\n"
        "Evidence JSON:\n"
        f"{json.dumps(evidence, ensure_ascii=False, indent=2)}"
    )


def build_trigger_detection_prompt(
    decision_record: dict[str, Any],
    evidence_packet: dict[str, Any],
) -> str:
    evidence = {
        "decision_record": {
            "ticker": decision_record.get("ticker"),
            "analysis_date": decision_record.get("analysis_date"),
            "review_due": decision_record.get("review_due"),
            "decision": decision_record.get("decision"),
            "thesis": decision_record.get("thesis"),
            "key_risk_triggers": decision_record.get("key_risk_triggers") or [],
            "prediction_checklist": decision_record.get("prediction_checklist") or [],
        },
        "daily_evidence": evidence_packet,
    }
    return (
        "You are doing a DAILY Key Risk Trigger check for a Korean equity self-loop.\n"
        "Do not score the full thesis unless a trigger has actually fired. "
        "Compare the prior key_risk_triggers against today's evidence only. "
        "A trigger is fired only when the evidence directly satisfies a concrete trigger condition; "
        "otherwise mark not_fired. If evidence is insufficient, mark uncertain.\n"
        "Return strict JSON only with this schema:\n"
        "{\n"
        '  "status": "fired|not_fired|uncertain",\n'
        '  "trigger_fired": true,\n'
        '  "matched_triggers": ["trigger text that fired"],\n'
        '  "reasoning": "short evidence-based rationale with exact levels/data when available",\n'
        '  "confidence": "low|medium|high"\n'
        "}\n\n"
        "Evidence JSON:\n"
        f"{json.dumps(evidence, ensure_ascii=False, indent=2)}"
    )


def build_lesson_summary_prompt(
    *,
    ticker: str,
    lessons: list[dict[str, Any]],
    previous_summary: str = "",
) -> str:
    return (
        "You are maintaining a long-term self-improvement memory for a Korean equity research agent.\n"
        "Summarize recurring mistakes and durable lessons. Do not include private secrets. "
        "Keep it concise and useful for future analysis prompts.\n"
        "Return Markdown only with sections:\n"
        "# Self-loop lesson summary\n"
        "## Recurring mistakes\n"
        "## Durable rules for next analyses\n"
        "## Watch items\n\n"
        f"Ticker: {ticker}\n\n"
        f"Previous summary:\n{previous_summary or '(none)'}\n\n"
        "Lesson JSONL rows:\n"
        f"{json.dumps(lessons, ensure_ascii=False, indent=2)}"
    )


def parse_review_response(text: str) -> dict[str, Any]:
    payload = _extract_json(text)
    overall = str(payload.get("overall", "uncertain")).strip().lower()
    if overall not in VALID_OUTCOMES:
        overall = "uncertain"
    confidence = str(payload.get("confidence", "medium")).strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    lesson = payload.get("lesson")
    if lesson is not None:
        lesson = str(lesson).strip() or None
    return {
        "overall": overall,
        "reasoning": str(payload.get("reasoning") or "").strip(),
        "checklist_results": _normalize_checklist_results(payload.get("checklist_results")),
        "lesson": lesson,
        "confidence": confidence,
    }


def parse_trigger_detection_response(text: str) -> dict[str, Any]:
    payload = _extract_json(text)
    status = str(payload.get("status") or "").strip().lower()
    if status not in VALID_TRIGGER_STATUSES:
        status = "uncertain"
    trigger_fired = bool(payload.get("trigger_fired"))
    if status == "fired":
        trigger_fired = True
    elif status in {"not_fired", "uncertain"}:
        trigger_fired = False
    confidence = str(payload.get("confidence") or "medium").strip().lower()
    if confidence not in VALID_CONFIDENCE:
        confidence = "medium"
    return {
        "status": status,
        "trigger_fired": trigger_fired,
        "matched_triggers": _as_str_list(payload.get("matched_triggers")),
        "reasoning": str(payload.get("reasoning") or "").strip(),
        "confidence": confidence,
    }


def _normalize_checklist_results(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "uncertain").strip().lower()
        if status not in VALID_OUTCOMES:
            status = "uncertain"
        item = " ".join(str(entry.get("item") or "").split())
        if not item:
            continue
        out.append({
            "item": item,
            "status": status,
            "reason": " ".join(str(entry.get("reason") or "").split()),
        })
    return out


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI review response must be a JSON object")
    return data
