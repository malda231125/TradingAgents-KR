#!/usr/bin/env python3
"""Fact-check a TradingAgents-KR Notion report against a later actual market packet.

Examples:
  python factcheck_notion_report.py --url "https://notion.example/report-page"
  python factcheck_notion_report.py --url "..." --check-date 2026-06-13 --publish
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_analysis_to_notion import (  # noqa: E402
    DEFAULT_PARENT_PAGE_ID,
    DEFAULT_REPO,
    NOTION_VERSION,
    configure_codex_home,
    markdown_to_blocks,
    notion_headers,
    notion_request,
    notion_token,
    publish_to_notion,
)

KST = ZoneInfo("Asia/Seoul")


def today_kst() -> str:
    return dt.datetime.now(KST).date().isoformat()


def parse_page_id(value: str) -> str:
    """Extract a Notion page UUID from app/notion URLs or raw IDs."""
    raw = value.strip()
    m = re.fullmatch(r"[0-9a-fA-F]{32}", raw.replace("-", ""))
    if m:
        h = raw.replace("-", "")
        return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"

    parsed = urllib.parse.urlparse(raw)
    candidates = [parsed.path, parsed.fragment, parsed.query, raw]
    for candidate in candidates:
        # Notion URLs usually end with a 32-char page id, sometimes after a slug hyphen.
        m = re.search(r"([0-9a-fA-F]{32})(?:[/?#]|$)", candidate)
        if m:
            h = m.group(1)
            return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
        m = re.search(
            r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
            candidate,
        )
        if m:
            return m.group(1)
    raise SystemExit(f"Could not extract Notion page id from: {value}")


def rich_text_plain(items) -> str:
    if not isinstance(items, list):
        return ""
    return "".join((rt or {}).get("plain_text", "") for rt in items if isinstance(rt, dict))


def block_to_text(block: dict) -> str:
    typ = block.get("type")
    obj = block.get(typ, {}) if typ else {}
    if not isinstance(obj, dict):
        return ""
    if typ in {"heading_1", "heading_2", "heading_3"}:
        marks = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[typ]
        return f"{marks} {rich_text_plain(obj.get('rich_text'))}".strip()
    if typ == "paragraph":
        return rich_text_plain(obj.get("rich_text"))
    if typ == "bulleted_list_item":
        return "- " + rich_text_plain(obj.get("rich_text"))
    if typ == "numbered_list_item":
        return "1. " + rich_text_plain(obj.get("rich_text"))
    if typ == "code":
        return "```\n" + rich_text_plain(obj.get("rich_text")) + "\n```"
    if typ == "quote":
        return "> " + rich_text_plain(obj.get("rich_text"))
    if typ == "child_page":
        return "# " + str(obj.get("title", ""))
    return rich_text_plain(obj.get("rich_text"))


def fetch_children(block_id: str, token: str) -> list[dict]:
    out: list[dict] = []
    cursor = None
    while True:
        path = f"blocks/{block_id}/children?page_size=100"
        if cursor:
            path += "&start_cursor=" + urllib.parse.quote(cursor)
        data = notion_request("GET", path, token)
        out.extend(data.get("results", []))
        if not data.get("has_more"):
            return out
        cursor = data.get("next_cursor")


def fetch_page_markdown(page_id: str, token: str) -> tuple[str, str]:
    page = notion_request("GET", f"pages/{page_id}", token)
    title = "TradingAgents report"
    props = page.get("properties") or {}
    for prop in props.values():
        if prop.get("type") == "title":
            t = rich_text_plain(prop.get("title"))
            if t:
                title = t
                break

    lines: list[str] = []

    def walk(block_id: str, depth: int = 0) -> None:
        for block in fetch_children(block_id, token):
            text = block_to_text(block)
            if text:
                lines.append(text)
                lines.append("")
            if block.get("has_children") and depth < 5:
                walk(block["id"], depth + 1)

    walk(page_id)
    return title, "\n".join(lines).strip()


def infer_report_metadata(markdown: str, title: str = "") -> dict:
    joined = title + "\n" + markdown
    ticker = None
    trade_date = None
    signal = None

    m = re.search(r"TradingAgents Run —\s*([^/\n]+?)\s*/\s*(\d{4}-\d{2}-\d{2})", joined)
    if m:
        ticker = m.group(1).strip()
        trade_date = m.group(2)

    if not ticker:
        m = re.search(r"\b(\d{6})\b", joined)
        if m:
            ticker = m.group(1)
    if not trade_date:
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", joined)
        if m:
            trade_date = m.group(1)

    m = re.search(r"Final signal\s*\|\s*\*\*?([A-Z]+)\*\*?", joined)
    if not m:
        m = re.search(r"Final signal\s+([A-Z]+)", joined)
    if not m:
        m = re.search(r"FINAL TRANSACTION PROPOSAL:\s*\*\*([A-Z]+)\*\*", joined)
    if m:
        signal = m.group(1).strip()

    if not ticker or not trade_date:
        raise SystemExit("Could not infer ticker/trade_date from the Notion report. Pass --ticker and --report-date.")
    return {"ticker": ticker, "trade_date": trade_date, "signal": signal}


def next_weekday(date_s: str) -> str:
    d = dt.date.fromisoformat(date_s) + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def get_actual_packet(repo: Path, ticker: str, check_date: str) -> dict:
    py = repo / ".venv" / "bin" / "python"
    if not py.exists():
        raise SystemExit(f"venv python not found: {py}")
    snippet = r'''
import json, sys
from dataclasses import asdict
from dotenv import load_dotenv
load_dotenv('.env')
from tradingagents.dataflows.prefetch import prefetch_market_packet
p = prefetch_market_packet(sys.argv[1], sys.argv[2])
print(json.dumps(asdict(p), ensure_ascii=False))
'''
    result = subprocess.run(
        [str(py), "-c", snippet, ticker, check_date],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    if result.returncode != 0:
        raise SystemExit(f"Failed to fetch actual packet\n{result.stderr[-3000:]}\n{result.stdout[-1000:]}")
    return json.loads(result.stdout)


def run_codex_factcheck(report_md: str, meta: dict, actual_packet: dict, check_date: str, model: str, timeout_s: int) -> str:
    # Keep prompt bounded. The original report can be very long.
    excerpts = report_md[:18000]
    packet_json = json.dumps(actual_packet, ensure_ascii=False, indent=2)
    if len(packet_json) > 14000:
        packet_json = packet_json[:14000] + "\n...TRUNCATED..."

    prompt = f"""You are a Korea equity trading report fact-checker.

Compare yesterday/past TradingAgents report against later actual market data.
Write in Korean, concise but specific.

Report metadata:
- ticker: {meta.get('ticker')}
- report_date: {meta.get('trade_date')}
- reported_final_signal: {meta.get('signal')}
- actual_check_date: {check_date}

Tasks:
1. Extract the main predicted signals/conditions from the report: direction, trend, volume confirmation, support/resistance, risk triggers, final stance.
2. Compare them with the actual market packet for the check date.
3. Mark each major claim as: 맞음 / 부분적 / 다름 / 확인불가.
4. If different, explain exactly what changed in price, volume, regime, moving averages, sector relative strength, volatility, or macro context.
5. End with a practical verdict: report quality, what to update in the thesis, and whether the previous signal should be maintained/softened/reversed.
6. Do not invent facts outside the report and packet.

Original report excerpt:
```markdown
{excerpts}
```

Actual market packet for check date:
```json
{packet_json}
```
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False, encoding="utf-8") as out:
        out_path = out.name
    try:
        env = os.environ.copy()
        configure_codex_home(env)
        proc = subprocess.run(
            ["codex", "exec", "-m", model, prompt, "-o", out_path],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            raise SystemExit(f"Codex factcheck failed with exit {proc.returncode}\n{proc.stdout[-4000:]}")
        text = Path(out_path).read_text(encoding="utf-8").strip()
        if not text:
            raise SystemExit(f"Codex returned empty factcheck output\n{proc.stdout[-2000:]}")
        return text
    finally:
        try:
            Path(out_path).unlink()
        except OSError:
            pass


def build_output_markdown(title: str, meta: dict, check_date: str, analysis: str, actual_packet: dict) -> str:
    price = actual_packet.get("price") or {}
    regime = actual_packet.get("regime") or {}
    signals = actual_packet.get("signals") or []
    lines = [
        f"# TradingAgents 리포트 팩트체크 — {meta.get('ticker')} / {meta.get('trade_date')} → {check_date}",
        "",
        "## 기준",
        "",
        f"- 원본 리포트: {title}",
        f"- 종목: {meta.get('ticker')}",
        f"- 원본 분석일: {meta.get('trade_date')}",
        f"- 원본 최종 시그널: {meta.get('signal') or '확인불가'}",
        f"- 실제 확인일: {check_date}",
        "",
        "## 실제 데이터 스냅샷",
        "",
        f"- 종가/현재 기준 가격: {price.get('close')}",
        f"- 1일 변화율: {price.get('change_1d_pct')}%",
        f"- 5일 변화율: {price.get('change_5d_pct')}%",
        f"- 20일 변화율: {price.get('change_20d_pct')}%",
        f"- Regime: {regime.get('label')} — {regime.get('description')}",
        "",
    ]
    if signals:
        lines.append("### 실제 패킷 시그널")
        lines.append("")
        for s in signals[:12]:
            lines.append(f"- {s}")
        lines.append("")
    lines.extend(["## 팩트체크 결과", "", analysis.strip(), ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", "--page-url", dest="url", required=True, help="Notion report URL or page id")
    parser.add_argument("--ticker", help="Override ticker if the report cannot be parsed")
    parser.add_argument("--report-date", help="Override original report date")
    parser.add_argument("--check-date", help="Actual date to check; default is next weekday after report date, capped by today")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--model", default=os.getenv("TRADINGAGENTS_FACTCHECK_MODEL", "gpt-5.5"))
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--publish", action="store_true", help="Publish the factcheck result to Notion and return URL")
    parser.add_argument("--parent-page-id", default=os.getenv("TRADINGAGENTS_NOTION_PARENT_PAGE_ID", DEFAULT_PARENT_PAGE_ID))
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    token = notion_token(repo)

    page_id = parse_page_id(args.url)
    title, report_md = fetch_page_markdown(page_id, token)
    meta = infer_report_metadata(report_md, title)
    if args.ticker:
        meta["ticker"] = args.ticker
    if args.report_date:
        meta["trade_date"] = args.report_date

    today = today_kst()
    default_check = next_weekday(meta["trade_date"])
    if default_check > today:
        default_check = today
    check_date = args.check_date or default_check

    actual_packet = get_actual_packet(repo, meta["ticker"], check_date)
    analysis = run_codex_factcheck(report_md, meta, actual_packet, check_date, args.model, args.timeout)
    output_md = build_output_markdown(title, meta, check_date, analysis, actual_packet)

    result = {
        "ticker": meta["ticker"],
        "report_date": meta["trade_date"],
        "check_date": check_date,
        "source_page_id": page_id,
        "analysis_markdown": output_md,
    }

    if args.publish:
        out_title = f"TradingAgents 팩트체크 — {meta['ticker']} / {meta['trade_date']} → {check_date}"
        url = publish_to_notion(output_md, out_title, args.parent_page_id, repo)
        result["notion_url"] = url
        # Avoid dumping long markdown when published.
        result.pop("analysis_markdown", None)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
