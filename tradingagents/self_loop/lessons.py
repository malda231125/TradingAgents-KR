from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def lesson_path(base_dir: str | Path, ticker: str) -> Path:
    return Path(base_dir) / "lessons" / f"{ticker}.jsonl"


def lesson_summary_path(base_dir: str | Path, ticker: str) -> Path:
    return Path(base_dir) / "lessons" / f"{ticker}.summary.md"


def append_lesson(
    *,
    ticker: str,
    lesson: str,
    source: dict[str, Any] | None = None,
    base_dir: str | Path = ".",
) -> Path:
    path = lesson_path(base_dir, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "lesson": lesson,
        "source": source or {},
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def load_lessons(
    ticker: str,
    *,
    base_dir: str | Path = ".",
    limit: int | None = 5,
) -> list[dict[str, Any]]:
    path = lesson_path(base_dir, ticker)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit is None:
        return rows
    return rows[-int(limit):]


def load_lesson_summary(
    ticker: str,
    *,
    base_dir: str | Path = ".",
) -> str:
    path = lesson_summary_path(base_dir, ticker)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def save_lesson_summary(
    ticker: str,
    summary: str,
    *,
    base_dir: str | Path = ".",
) -> Path:
    path = lesson_summary_path(base_dir, ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summary.strip() + "\n", encoding="utf-8")
    return path


def format_lessons_context(lessons: list[dict[str, Any]], *, summary: str = "") -> str:
    if not lessons and not summary:
        return ""
    lines = [
        "Self-loop lessons from prior analyses:",
    ]
    if summary:
        lines.extend(["", "Long-term lesson summary:", summary.strip(), "", "Recent lessons:"])
    for item in lessons:
        lesson = str(item.get("lesson") or "").strip()
        if lesson:
            lines.append(f"- {lesson}")
    return "\n".join(lines)
