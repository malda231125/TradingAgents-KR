#!/usr/bin/env python3
"""Run TradingAgents-KR self-loop analysis and publish the report to Notion.

Examples:
  python run_analysis_to_notion.py --query "삼성전자 오늘 주식 분석해줘"
  python run_analysis_to_notion.py --ticker 005930 --date 2026-06-12
  python run_analysis_to_notion.py --report-path /path/complete_report.md --skip-run --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DEFAULT_REPO = Path(__file__).resolve().parents[4]
DEFAULT_WORKSPACE = DEFAULT_REPO.parent
DEFAULT_NOTION_ENV = DEFAULT_WORKSPACE / "secret_files" / "notion.env"
DEFAULT_CODEX_HOME = Path.home() / ".codex"
DEFAULT_PARENT_PAGE_ID = ""  # No public default; set via TRADINGAGENTS_NOTION_PAGE_ID in .env.
NOTION_VERSION = "2026-03-11"

COMMON_KR_TICKERS = {
    "삼성전자": "005930",
    "삼전": "005930",
    "SK하이닉스": "000660",
    "하이닉스": "000660",
    "현대차": "005380",
    "기아": "000270",
    "NAVER": "035420",
    "네이버": "035420",
    "카카오": "035720",
    "LG에너지솔루션": "373220",
    "엘지에너지솔루션": "373220",
    "셀트리온": "068270",
    "POSCO홀딩스": "005490",
    "포스코홀딩스": "005490",
    "삼성바이오로직스": "207940",
    "삼성SDI": "006400",
    "LG화학": "051910",
    "현대모비스": "012330",
}


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def notion_token(repo: Path) -> str:
    for key in ("NOTION_API_TOKEN", "NOTION_API_KEY"):
        value = os.getenv(key)
        if value:
            return value
    for env_path in (repo / ".env", DEFAULT_NOTION_ENV):
        values = read_env_file(env_path)
        for key in ("NOTION_API_TOKEN", "NOTION_API_KEY"):
            value = values.get(key)
            if value:
                return value
    raise SystemExit(
        "NOTION_API_TOKEN is required. Set it in the environment or "
        f"{DEFAULT_NOTION_ENV}."
    )


def configure_codex_home(env: dict[str, str]) -> None:
    current = env.get("CODEX_HOME")
    if current and (Path(current).expanduser() / "auth.json").exists():
        return
    if (DEFAULT_CODEX_HOME / "auth.json").exists():
        env["CODEX_HOME"] = str(DEFAULT_CODEX_HOME)


def today_kst() -> str:
    return dt.datetime.now(KST).date().isoformat()


def parse_date(query: str | None, explicit: str | None) -> str:
    if explicit:
        return explicit
    if query:
        m = re.search(r"(20\d{2})[-./년\s]*(\d{1,2})[-./월\s]*(\d{1,2})", query)
        if m:
            y, mo, d = map(int, m.groups())
            return dt.date(y, mo, d).isoformat()
    return today_kst()


def resolve_ticker(repo: Path, query: str | None, explicit: str | None) -> tuple[str, str | None]:
    if explicit:
        return explicit.strip(), None
    if not query:
        raise SystemExit("ticker or query is required")

    m = re.search(r"\b(\d{6})\b", query)
    if m:
        return m.group(1), None

    normalized_query = query.replace(" ", "")
    for name, code in COMMON_KR_TICKERS.items():
        if name.replace(" ", "") in normalized_query:
            return code, name

    # Fall back to the repo's own ticker resolver if possible.
    py = repo / ".venv" / "bin" / "python"
    if py.exists():
        snippet = """
import sys
from dotenv import load_dotenv
load_dotenv('.env')
from tradingagents.dataflows.korea_ticker import get_stock_code
q = sys.argv[1]
print(get_stock_code(q) or '')
"""
        result = subprocess.run(
            [str(py), "-c", snippet, query],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        code = result.stdout.strip()
        if re.fullmatch(r"\d{6}", code):
            return code, query

    raise SystemExit(
        f"Could not resolve ticker from query: {query!r}. Pass --ticker 6-digit-code."
    )


def parse_self_loop_output(output: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in output.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in {
            "report_path",
            "decision_path",
            "digest_path",
            "retrospective_path",
            "signal",
            "ticker",
            "analysis_date",
        }:
            fields[key] = value
    return fields


def parse_daily_trigger_output(output: str) -> dict[str, str]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {
            "daily_trigger_check_status": "parse_error",
            "daily_trigger_check_error": output[-1000:],
        }
    fields = {
        "daily_trigger_check_status": "ok",
        "daily_trigger_check_path": str(payload.get("digest_path") or ""),
        "daily_trigger_check_count": str(len(payload.get("checked") or [])),
    }
    fired = [x for x in payload.get("checked") or [] if x.get("trigger_fired")]
    if fired:
        fields["daily_trigger_check_fired"] = ",".join(str(x.get("ticker")) for x in fired)
    return fields


def run_daily_trigger_check(repo: Path, py: Path, base_dir: Path, trade_date: str, env: dict[str, str], timeout_s: int) -> dict[str, str]:
    command = [
        str(py),
        "scripts/check_self_loop_triggers.py",
        "--base-dir",
        str(base_dir),
        "--as-of-date",
        trade_date,
    ]
    try:
        proc = subprocess.run(
            command,
            cwd=repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=min(timeout_s, 1800),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "daily_trigger_check_status": "timeout",
            "daily_trigger_check_error": str(exc),
        }
    output = proc.stdout or ""
    if proc.returncode != 0:
        return {
            "daily_trigger_check_status": "failed",
            "daily_trigger_check_error": output[-1000:],
        }
    return parse_daily_trigger_output(output)


def append_self_loop_artifacts(markdown: str, paths: dict[str, str]) -> str:
    sections = [markdown.rstrip()]
    daily_trigger_path = paths.get("daily_trigger_check_path")
    if daily_trigger_path:
        path = Path(daily_trigger_path)
        if path.exists():
            sections.extend(["", "---", "", "## Daily Trigger Check", "", path.read_text(encoding="utf-8").strip()])

    digest_path = paths.get("digest_path")
    if digest_path and digest_path != "None":
        path = Path(digest_path)
        if path.exists():
            sections.extend(["", "---", "", "## Self-loop Digest", "", path.read_text(encoding="utf-8").strip()])

    retrospective_path = paths.get("retrospective_path")
    if retrospective_path and retrospective_path != "None":
        path = Path(retrospective_path)
        if path.exists():
            sections.extend(["", "---", "", "## Prior Retrospective", "", path.read_text(encoding="utf-8").strip()])

    decision_path = paths.get("decision_path")
    if decision_path and decision_path != "None":
        path = Path(decision_path)
        if path.exists():
            sections.extend(
                [
                    "",
                    "---",
                    "",
                    "## Decision Record",
                    "",
                    "```json",
                    path.read_text(encoding="utf-8").strip(),
                    "```",
                ]
            )
    return "\n".join(sections).rstrip() + "\n"


def run_tradingagents(
    repo: Path,
    ticker: str,
    trade_date: str,
    timeout_s: int,
    *,
    self_loop: bool = True,
    self_loop_base_dir: Path | None = None,
    llm_provider: str | None = None,
    quick_model: str | None = None,
    deep_model: str | None = None,
    cli_effort: str | None = None,
    cli_max_retries: int | None = None,
) -> tuple[Path, str, float, dict[str, str]]:
    py = repo / ".venv" / "bin" / "python"
    if not py.exists():
        raise SystemExit(f"venv python not found: {py}")
    if not (repo / ".env").exists():
        raise SystemExit(f".env not found in repo: {repo}")

    env = os.environ.copy()
    configure_codex_home(env)
    env["TRADINGAGENTS_TIMING_LOGS"] = "1"
    # Formal reports must run through the full TradingAgents workflow using a
    # subscription CLI backend, not a direct OpenAI API-key fallback.
    if llm_provider:
        env["TRADINGAGENTS_LLM_PROVIDER"] = llm_provider
    else:
        env.setdefault("TRADINGAGENTS_LLM_PROVIDER", "codex-cli")

    provider = env.get("TRADINGAGENTS_LLM_PROVIDER", "codex-cli").strip().lower()
    if provider == "claude-cli":
        quick_default = "sonnet"
        deep_default = "opus-4.8"
        effort_default = "max"
    else:
        quick_default = "gpt-5.5"
        deep_default = "gpt-5.5"
        effort_default = None

    selected_quick = quick_model or env.get("TRADINGAGENTS_QUICK_MODEL") or quick_default
    selected_deep = deep_model or env.get("TRADINGAGENTS_DEEP_MODEL") or deep_default
    env["TRADINGAGENTS_QUICK_MODEL"] = selected_quick
    env["TRADINGAGENTS_DEEP_MODEL"] = selected_deep
    # Compatibility for older wrappers/configs that used the *_THINK_LLM names.
    env.setdefault("TRADINGAGENTS_QUICK_THINK_LLM", selected_quick)
    env.setdefault("TRADINGAGENTS_DEEP_THINK_LLM", selected_deep)

    env.setdefault("TRADINGAGENTS_CLI_TIMEOUT", str(max(timeout_s, 1800)))
    if cli_max_retries is not None:
        env["TRADINGAGENTS_CLI_MAX_RETRIES"] = str(cli_max_retries)
    if provider == "claude-cli":
        env.setdefault("TRADINGAGENTS_CLI_EFFORT", cli_effort or effort_default or "")
    else:
        if cli_effort:
            env["TRADINGAGENTS_CLI_EFFORT"] = cli_effort
        env.setdefault("CODEX_MODEL_REASONING_EFFORT", "xhigh")
    started = time.time()
    daily_trigger_fields: dict[str, str] = {}
    if self_loop:
        base_dir = self_loop_base_dir or (repo / "results" / "_self_loop")
        base_dir.mkdir(parents=True, exist_ok=True)
        daily_trigger_fields = run_daily_trigger_check(
            repo,
            py,
            base_dir,
            trade_date,
            env,
            timeout_s,
        )
        command = [
            str(py),
            "scripts/run_self_loop.py",
            "--ticker",
            ticker,
            "--date",
            trade_date,
            "--base-dir",
            str(base_dir),
        ]
    else:
        command = [str(py), "main.py", ticker, trade_date]

    proc = subprocess.run(
        command,
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_s,
    )
    elapsed = time.time() - started
    output = proc.stdout or ""
    if proc.returncode != 0:
        raise SystemExit(f"TradingAgents failed with exit {proc.returncode}\n{output[-4000:]}")

    loop_fields: dict[str, str] = {}
    if self_loop:
        loop_fields = parse_self_loop_output(output)
        loop_fields.update(daily_trigger_fields)
        report_value = loop_fields.get("report_path")
        report = Path(report_value).expanduser() if report_value else Path()
        if report and not report.is_absolute():
            report = repo / report
    else:
        report = repo / "results" / ticker / trade_date / "complete_report.md"
        if not report.exists():
            m = re.search(r"Complete report saved to:\s*(.+)", output)
            if m:
                report = Path(m.group(1).strip())
    if not report.exists():
        raise SystemExit(f"report not found for {ticker} {trade_date}")
    return report, output, elapsed, loop_fields


def notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def notion_request(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"https://api.notion.com/v1/{path}",
        data=data,
        method=method,
        headers=notion_headers(token),
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def rich_text_chunks(text: str, limit: int = 1900) -> list[dict]:
    chunks = []
    text = text or ""
    for i in range(0, len(text), limit):
        chunks.append({"type": "text", "text": {"content": text[i : i + limit]}})
    return chunks or [{"type": "text", "text": {"content": ""}}]


def paragraph_blocks(text: str) -> list[dict]:
    blocks = []
    for i in range(0, len(text), 1900):
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text_chunks(text[i:i+1900])},
        })
    return blocks


def code_block(text: str, language: str = "plain text") -> dict:
    # Notion code rich_text has the same 2000 char segment limit; chunk inside one block.
    return {
        "object": "block",
        "type": "code",
        "code": {"language": language, "rich_text": rich_text_chunks(text)},
    }


def markdown_to_blocks(markdown: str) -> list[dict]:
    blocks: list[dict] = []
    lines = markdown.splitlines()
    i = 0
    para: list[str] = []

    def flush_para():
        nonlocal para
        if para:
            text = "\n".join(para).strip()
            if text:
                blocks.extend(paragraph_blocks(text))
            para = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        if stripped.startswith("```"):
            flush_para()
            fence_lang = stripped.strip("`").strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            code = "\n".join(code_lines)
            # Split very large code blocks into multiple Notion code blocks.
            for j in range(0, len(code), 1800 * 5):
                blocks.append(code_block(code[j:j + 1800 * 5], fence_lang))
            continue

        if stripped.startswith("#"):
            flush_para()
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip() or "Untitled"
            block_type = "heading_1" if level == 1 else "heading_2" if level == 2 else "heading_3"
            blocks.append({
                "object": "block",
                "type": block_type,
                block_type: {"rich_text": rich_text_chunks(title[:1900])},
            })
            i += 1
            continue

        # Preserve markdown tables as code blocks. They are easier to read than lossy conversion.
        if stripped.startswith("|"):
            flush_para()
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl.append(lines[i])
                i += 1
            blocks.append(code_block("\n".join(tbl), "markdown"))
            continue

        if stripped.startswith(('- ', '* ')):
            flush_para()
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": rich_text_chunks(stripped[2:].strip())},
            })
            i += 1
            continue

        para.append(line)
        i += 1

    flush_para()
    return blocks


def append_blocks(page_id: str, token: str, blocks: list[dict]) -> None:
    for i in range(0, len(blocks), 100):
        notion_request("PATCH", f"blocks/{page_id}/children", token, {"children": blocks[i:i+100]})


def publish_to_notion(markdown: str, title: str, parent_page_id: str, repo: Path = DEFAULT_REPO) -> str:
    token = notion_token(repo)
    created = notion_request(
        "POST",
        "pages",
        token,
        {
            "parent": {"page_id": parent_page_id},
            "properties": {
                "title": [{"type": "text", "text": {"content": title[:1900]}}]
            },
        },
    )
    page_id = created["id"]
    blocks = markdown_to_blocks(markdown)
    append_blocks(page_id, token, blocks)
    return created.get("url") or f"https://www.notion.so/{page_id.replace('-', '')}"


def infer_report_metadata(markdown: str) -> tuple[str | None, str | None]:
    m = re.search(r"#\s*TradingAgents Run —\s*([^/]+?)\s*/\s*(\d{4}-\d{2}-\d{2})", markdown)
    if not m:
        return None, None
    return m.group(1).strip(), m.group(2).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="Natural-language request, e.g. 삼성전자 오늘 주식 분석해줘")
    parser.add_argument("--ticker", help="6-digit Korean stock code")
    parser.add_argument("--date", help="YYYY-MM-DD; defaults to today KST")
    parser.add_argument("--repo", default=str(DEFAULT_REPO))
    parser.add_argument("--timeout", type=int, default=7200, help="TradingAgents run timeout seconds; high-quality Codex runs may be silent for a long time")
    parser.add_argument(
        "--parent-page-id",
        # Honor the documented env var name first (`.env.example` / llm.txt use
        # TRADINGAGENTS_NOTION_PAGE_ID); keep the older *_PARENT_PAGE_ID name for
        # backward compatibility, then fall back to the built-in default.
        default=(
            os.getenv("TRADINGAGENTS_NOTION_PAGE_ID")
            or os.getenv("TRADINGAGENTS_NOTION_PARENT_PAGE_ID")
            or DEFAULT_PARENT_PAGE_ID
        ),
    )
    parser.add_argument("--skip-run", action="store_true", help="Publish an existing report instead of running main.py")
    parser.add_argument("--report-path", help="Existing Markdown report path for --skip-run or dry-run")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate without creating Notion page")
    parser.add_argument("--legacy-single-run", action="store_true", help="Run main.py directly instead of the self-loop workflow")
    parser.add_argument(
        "--llm-provider",
        choices=("codex-cli", "claude-cli"),
        help="CLI LLM backend for the analysis. Defaults to codex-cli unless TRADINGAGENTS_LLM_PROVIDER is set.",
    )
    parser.add_argument("--quick-model", help="Override quick model, e.g. gpt-5.5, sonnet")
    parser.add_argument("--deep-model", help="Override deep model, e.g. gpt-5.5, opus-4.8")
    parser.add_argument(
        "--cli-effort",
        help="CLI reasoning effort. For Claude CLI this is passed as --effort, e.g. max.",
    )
    parser.add_argument("--cli-max-retries", type=int, help="Override CLI max retry attempts")
    parser.add_argument(
        "--self-loop-base-dir",
        help="Directory for self-loop decisions/retrospectives/lessons; defaults to repo/results/_self_loop",
    )
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    resolved_name = None
    loop_fields: dict[str, str] = {}

    if args.skip_run:
        if not args.report_path:
            raise SystemExit("--report-path is required with --skip-run")
        report = Path(args.report_path).expanduser().resolve()
        if not report.exists():
            raise SystemExit(f"report not found: {report}")
        elapsed = 0.0
        markdown = report.read_text(encoding="utf-8")
        report_ticker, report_date = infer_report_metadata(markdown)
        if args.ticker:
            ticker = args.ticker.strip()
        elif report_ticker and re.fullmatch(r"\d{6}", report_ticker):
            ticker = report_ticker
        elif args.query:
            ticker, resolved_name = resolve_ticker(repo, args.query, None)
        else:
            raise SystemExit("Could not infer ticker from report. Pass --ticker.")
        trade_date = args.date or report_date or parse_date(args.query, None)
    else:
        ticker, resolved_name = resolve_ticker(repo, args.query, args.ticker)
        trade_date = parse_date(args.query, args.date)
        report, _output, elapsed, loop_fields = run_tradingagents(
            repo,
            ticker,
            trade_date,
            args.timeout,
            self_loop=not args.legacy_single_run,
            self_loop_base_dir=Path(args.self_loop_base_dir).expanduser().resolve()
            if args.self_loop_base_dir
            else None,
            llm_provider=args.llm_provider,
            quick_model=args.quick_model,
            deep_model=args.deep_model,
            cli_effort=args.cli_effort,
            cli_max_retries=args.cli_max_retries,
        )
        markdown = report.read_text(encoding="utf-8")
        if loop_fields:
            markdown = append_self_loop_artifacts(markdown, loop_fields)
    title_name = resolved_name or ticker
    title_kind = "자가개선 루프 분석" if loop_fields else "주식 분석"
    title = f"TradingAgents {title_kind} — {title_name}({ticker}) / {trade_date}"

    if args.dry_run:
        blocks = markdown_to_blocks(markdown)
        print(json.dumps({
            "ticker": ticker,
            "trade_date": trade_date,
            "report_path": str(report),
            "decision_path": loop_fields.get("decision_path"),
            "retrospective_path": loop_fields.get("retrospective_path"),
            "digest_path": loop_fields.get("digest_path"),
            "daily_trigger_check_path": loop_fields.get("daily_trigger_check_path"),
            "daily_trigger_check_status": loop_fields.get("daily_trigger_check_status"),
            "signal": loop_fields.get("signal"),
            "title": title,
            "notion_blocks": len(blocks),
            "elapsed_seconds": round(elapsed, 2),
            "dry_run": True,
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.parent_page_id:
        print(
            "ERROR: no Notion parent page id. Set TRADINGAGENTS_NOTION_PAGE_ID in "
            ".env (or pass --parent-page-id). See docs/api-keys.md for the Notion "
            "integration setup.",
            file=sys.stderr,
        )
        return 2

    url = publish_to_notion(markdown, title, args.parent_page_id, repo)
    print(json.dumps({
        "ticker": ticker,
        "trade_date": trade_date,
        "report_path": str(report),
        "decision_path": loop_fields.get("decision_path"),
        "retrospective_path": loop_fields.get("retrospective_path"),
        "digest_path": loop_fields.get("digest_path"),
        "daily_trigger_check_path": loop_fields.get("daily_trigger_check_path"),
        "daily_trigger_check_status": loop_fields.get("daily_trigger_check_status"),
        "signal": loop_fields.get("signal"),
        "notion_url": url,
        "elapsed_seconds": round(elapsed, 2),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
