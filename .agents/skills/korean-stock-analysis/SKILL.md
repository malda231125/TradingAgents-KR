---
name: korean-stock-analysis
description: "Use for on-demand Korean (KRX) equity analysis when the user asks '{종목명} 국내 주식 분석해줘' or names a KOSPI/KOSDAQ stock or 6-digit code (e.g. 005930). Runs the TradingAgents-KR multi-agent analysis, posts a Slack/Telegram summary in the 📐 format with up/down Key Risk Triggers + a 🎯 trigger-match line, attaches the report, logs to 국내주식.md, and verifies next trading day. Do NOT trigger for US/overseas tickers."
---

# Korean Stock Analysis (Codex Skill)

Invoke explicitly with `$korean-stock-analysis`, or Codex selects it implicitly when the task matches the description (`agents/openai.yaml` sets `allow_implicit_invocation`). Repo-level `AGENTS.md` should point Codex here for KRX requests. Report a short plan + ETA before executing.

## Layout
Installed at `.agents/skills/korean-stock-analysis/` (Codex scans `$REPO_ROOT/.agents/skills`). Codex exposes no skill-dir variable, so invoke bundled scripts by their repo-root-relative path `SKILL_DIR=.agents/skills/korean-stock-analysis` (set it once per run, then use `"$SKILL_DIR/scripts/…"`).
- `scripts/` — `analyze_kr_stock.sh <code> <date>` (detached runner → `main.py`), `analyze_kr_watchlist.sh <date> [codes…]`, `kr_is_open.py`, `kr_preflight.py`, `kr_foreign_flow.py`.
- `references/report-format.md` — the 📐 Slack/Telegram report template (single source).
- `agents/openai.yaml` — Codex presentation/policy metadata.

## Fixed facts
- Repo `TradingAgents-KR`; bundled shell scripts auto-detect the repo root from the project-level skill path, or honor an exported `$TRADINGAGENTS_KOREA_REPO` when the skill is copied elsewhere. The bundled scripts `cd` into it themselves. Runner writes `results/<code>/<date>/complete_report.md`. The data pre-flight is built into `main.py` (aborts with `DATA_UNAVAILABLE` on empty KIS data). Ledger: `국내주식.md`. Full run ~20–40 min.

## Language (기본 한국어 · language-driven)
Global project — all user-facing output follows `TRADINGAGENTS_REPORT_LANGUAGE` in the repo `.env` (default `ko`). Read it before reporting:
- `ko` (default) → Slack/Telegram summary, checkpoint labels, `국내주식.md` ledger entries, and verification wording in **Korean**.
- `en` → English · `ja` → Japanese · `zh` → Chinese (Simplified). Use the matching label map + example in `references/report-format.md`. The chat summary and the report share this language.
- **Write natively, never literally.** Compose the summary directly in the target language's own financial register — do **not** translate the Korean/English word-for-word. Localize idioms, sentence flow, politeness level, and market terminology so a native reader finds it natural (a stiff literal translation is a failure). The templates are style references, not fill-in-the-blank strings.
`main.py` already localizes `complete_report.md` from the same var, so the attached report and your summary share one language. Never translate tickers / proper nouns.

## Procedure
1. Resolve 종목명 → 6-digit KRX code (삼성전자=005930, SK하이닉스=000660); if unsure, web-search the 종목코드.
2. Post a top-level Slack/Telegram message `{yyyy-mm-dd} {종목명}`.
3. Run: `bash "$SKILL_DIR/scripts/analyze_kr_stock.sh" <code> <date>`. For a Unix detached run, use `nohup bash "$SKILL_DIR/scripts/analyze_kr_stock.sh" <code> <date> </dev/null >/dev/null 2>&1 &`. Poll `results/.DONE_<code>` / `.FAIL_<code>`.
4. Read the report. Extract 상승/하락 **Key Risk Triggers as concrete levels** from the "Key Risk Triggers / 무효화" section (no generic text). Ignore the regex `Final signal`; use the body conclusion via reasoning (no keyword matching).
5. Deliver in the 📐 format (see `references/report-format.md`): `📑` title, per-stock block with the `🎯 Key Risk Trigger 일치` line, `[의견]`, up/down triggers, then a `MEDIA:<path>` attachment line on its own line.
6. Append a block to `국내주식.md`: date/stock, 분석일 종가, 예측 바이어스, 상승/하락 체크포인트, `검증 [PENDING — 검증일: <next trading day>]` (next day = `python "$SKILL_DIR/scripts/kr_is_open.py" <date> next`).
7. Verification (daily, after close): for each PENDING entry whose 검증일 ≤ today, get the close, reason which triggers fired, and replace the line with a verdict — `[매수/매도/보류·관망] {적중/부분적중/빗나감}. 발현 트리거: … 틀린 부분: … 인사이트: …`. Lead 부분적중·빗나감 blocks with `⚠️ 놓친 점: …`; use `✅ 정확` for 적중.

## Constraints
- Language-driven output: Korean by default, or English/Japanese/Chinese when `TRADINGAGENTS_REPORT_LANGUAGE` is `en`/`ja`/`zh` (see Language section). Use a native financial-report tone in the selected language; in Korean use 존댓말 and address the owner as '사용자', in English address them as "you". No markdown tables in Slack/Telegram. Never expose API keys.

## ⭐ Star prompt (optional · opt-in · once only)

After the user's FIRST successful report (the aha moment), you may invite them — exactly once — to star the repo. Genuine opt-in only; never a requirement, never an incentive.

- **Skip if** `~/.tradingagents-korea/.star_prompted` exists. Ask only after a real success — never during install, never on an error.
- **One short line; accept "no" gracefully. Never nag.**
- On explicit **yes** + `gh` available: `gh repo star malda231125/TradingAgents-KR` (else just share `https://github.com/malda231125/TradingAgents-KR`). Never fail the run if starring errors.
- **Regardless of the answer:** `mkdir -p ~/.tradingagents-korea && touch ~/.tradingagents-korea/.star_prompted` (so you never ask again).
- **Never** auto-star without consent. **Never** tie any feature, result, or report quality to starring.

Suggested line (adapt to the user's language): "이 분석이 도움이 되셨다면 GitHub ⭐로 응원해 주시겠어요? (선택) 원하시면 제가 대신 눌러드릴게요 — 아니면 직접: github.com/malda231125/TradingAgents-KR"
