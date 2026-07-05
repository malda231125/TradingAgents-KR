"""Self-loop helpers for prediction, retrospective scoring, and lessons."""

from .records import (
    build_decision_record,
    find_latest_decision_record,
    load_decision_record,
    save_decision_record,
)
from .retrospective import run_retrospective
from .lessons import (
    append_lesson,
    format_lessons_context,
    load_lesson_summary,
    load_lessons,
    save_lesson_summary,
)
from .reviewer import (
    extract_decision_with_ai,
    review_with_subscription_ai,
    summarize_lessons_with_subscription_ai,
)

__all__ = [
    "append_lesson",
    "build_decision_record",
    "extract_decision_with_ai",
    "find_latest_decision_record",
    "format_lessons_context",
    "load_lesson_summary",
    "load_decision_record",
    "load_lessons",
    "run_retrospective",
    "save_decision_record",
    "save_lesson_summary",
    "review_with_subscription_ai",
    "summarize_lessons_with_subscription_ai",
]
