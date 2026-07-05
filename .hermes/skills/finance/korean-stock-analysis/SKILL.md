---
name: korean-stock-analysis
description: On-demand Korean (KRX) equity analysis via TradingAgents-KR — multi-agent analysis, Slack/Telegram report in the 📐 format with up/down Key Risk Triggers and a 🎯 trigger-match line, trend logging to 국내주식.md, and next-trading-day verification. Triggers on "{종목명} 국내 주식 분석해줘" or a 6-digit KRX code (e.g. 005930). Not for US/overseas tickers.
version: 1.0.0
author: TradingAgents Korea
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Finance, Equities, Korea, KRX, Analysis]
    related_skills: [us-stock-analysis]
    requires_tools: [terminal, process, file]
    config:
      - key: tradingagents.korea.repo
        description: "Path to the TradingAgents-KR repo (exported as TRADINGAGENTS_KOREA_REPO)"
        default: "$HOME/TradingAgents-KR"
        prompt: "TradingAgents-KR repo path?"
    blueprint:
      # Open-session analysis on KRX trading days (09:01 KST); report follows separately.
      schedule: "1 9 * * 1-5"
      deliver: origin
      prompt: "삼성전자(005930)·SK하이닉스(000660) 국내 워치리스트 분석을 실행하고 📐 포맷으로 보고하라."
      no_agent: false
required_environment_variables:
  - name: KIS_APP_KEY
    prompt: "Korea Investment & Securities API app key"
    help: "https://apiportal.koreainvestment.com"
    required_for: "KRX price/volume/flow data"
  - name: KIS_APP_SECRET
    prompt: "Korea Investment & Securities API app secret"
    required_for: "KRX price/volume/flow data"
---

# Korean Stock Analysis

## When to Use
Load when the owner asks **"{종목명} 국내 주식 분석해줘"** (or 국내주식/한국주식/코스피/코스닥/KRX, or a 6-digit code like `005930`). Do **not** use for US/overseas tickers (see `us-stock-analysis`). Always state a short plan + ETA first.

## Language (기본 한국어 · language-driven)
Global project — all user-facing output (Slack/Telegram summary, checkpoint labels, `국내주식.md` ledger, verification wording) follows `TRADINGAGENTS_REPORT_LANGUAGE` in the repo `.env` (default `ko`): `ko` → Korean (the 📐 format below) · `en` → English · `ja` → Japanese · `zh` → Chinese (Simplified). `main.py` already localizes `complete_report.md` from the same var, so report and summary share one language. Never translate tickers / proper nouns.
- **Write natively, never literally.** Compose the summary directly in the target language's own financial register (native terminology, idioms, politeness level) — do **not** translate the Korean word-for-word; a stiff literal translation is a failure. The label maps below are anchors, not the whole sentence.
- EN: 간단한 요약→Summary · 상승 체크포인트→Upside checkpoints · 하락 체크포인트→Downside checkpoints · `🎯 Key Risk Trigger 일치`→`🎯 Key Risk Trigger match` · 미발현(중간구간)→not triggered (mid-range) · `[의견: 매수/매도/보류]`→`[View: Buy / Sell / Hold]` · 특이→Note · 결론→Conclusion · 검증일→Verify date · 적중/부분적중/빗나감→Hit / Partial / Miss · `✅ 정확`→`✅ Accurate` · `⚠️ 놓친 점`→`⚠️ Missed` · 발현 트리거→Fired triggers · 인사이트→Insight.
- JA: 상승/하락→上値／下値 · `🎯 …일치`→`🎯 キーリスクトリガー` · 미발현(중간구간)→未達（レンジ内） · `[의견: 매수/매도/보류]`→`[判断: 買い/売り/様子見]` · 특이→注目 · 결론→結論 · 검증일→検証日 · 적중/부분적중/빗나감→的中/一部的中/外れ · `✅ 정확`→`✅ 的中` · `⚠️ 놓친 점`→`⚠️ 見落とし` · [장마감]→[大引け]. Style: です・ます調, 証券レポートの語彙.
- ZH: 상승/하락→上行／下行 · `🎯 …일치`→`🎯 关键风险触发` · 미발현(중간구간)→未触发（区间内） · `[의견: 매수/매도/보류]`→`[观点: 买入/卖出/观望]` · 특이→备注 · 결론→结论 · 검증일→验证日 · 적중/부분적중/빗나감→命中/部分命中/落空 · `✅ 정확`→`✅ 命中` · `⚠️ 놓친 점`→`⚠️ 遗漏` · [장마감]→[收盘]. Style: 简体, 券商研报术语.

## Quick Reference
| Action | Command |
| --- | --- |
| Run analysis (single) | `bash ${HERMES_SKILL_DIR}/scripts/analyze_kr_stock.sh <code> <yyyy-mm-dd>` |
| Run watchlist (multi) | `bash ${HERMES_SKILL_DIR}/scripts/analyze_kr_watchlist.sh <date> [codes…]` |
| Is today a trading day? | `python3 ${HERMES_SKILL_DIR}/scripts/kr_is_open.py <date>` → OPEN/CLOSED |
| Next trading day | `python3 ${HERMES_SKILL_DIR}/scripts/kr_is_open.py <date> next` |
| Foreign/inst. flow | `python3 ${HERMES_SKILL_DIR}/scripts/kr_foreign_flow.py <code> [days]` |

The repo path comes from `$TRADINGAGENTS_KOREA_REPO` (config `tradingagents.korea.repo`); bundled scripts default to `$HOME/TradingAgents-KR` when unset. Output: `results/<code>/<date>/complete_report.md`. The data pre-flight is built into `main.py` (aborts on empty KIS packets). Ledger: `국내주식.md`. Full run ~20–40 min.

## Procedure
1. Resolve 종목명 → 6-digit KRX code (삼성전자=005930, SK하이닉스=000660); if unsure, `web_search "{종목명} 종목코드"`.
2. Post a header `{yyyy-mm-dd} {종목명}`.
3. Run the analysis detached; wait on `results/.DONE_<code>` / `.FAIL_<code>`.
4. Read the report; extract 상승/하락 **Key Risk Triggers as concrete levels** from the "Key Risk Triggers / 무효화" section. Ignore the regex `Final signal`; reason from the body conclusion (no keyword matching).
5. Deliver in the 📐 format — `📑 {날짜} {종목} [{세션}]`, per-stock block with a **`🎯 Key Risk Trigger 일치`** line (발현 레벨+방향 or `미발현(중간구간)`), `[의견: 매수/매도/보류]`, up/down triggers, 특이점. **Attach the full report as a document with the `[[as_document]]` directive** (Hermes upload), pointing at `results/<code>/<date>/complete_report.md`.
6. Append a block to `국내주식.md`; set `검증 [PENDING — 검증일: <next trading day>]` (next day = `kr_is_open.py <date> next`).
7. Daily verification (after close) scores each PENDING entry whose 검증일 ≤ today: get the close, reason which Key Risk Triggers fired, write a verdict (`[매수/매도/보류·관망] {적중/부분적중/빗나감}. 발현 트리거 … 틀린 부분 … 인사이트 …`), and surface it as `🔁 self-loop {종목}: {status}`. (The repo also ships `scripts/self_loop_review.py <code> <date> --trigger-fired` for an internal AI-scored retrospective when the self-loop decision record is used.)

## Pitfalls
- **Pre-open empty data**: querying before the session settles returns empty KIS packets → no_data reports. `main.py`'s built-in pre-flight aborts on empty packets; schedule at/after open.
- **Trusting `Final signal`**: it is a regex label that often disagrees with the body — always use the body conclusion.
- **Generic checkpoints**: triggers must be concrete report levels (e.g. "MA20 329,275 거래량 동반 종가 이탈"), never generic phrases.
- **Tables in Slack/Telegram / exposing API keys**: forbidden. Use bullets; keep keys server-side. Use a native financial-report tone in the selected language; Korean: 존댓말 + address as '사용자'; English: polite, address the user as "you"; Japanese/Chinese: natural finance-register prose, never literal translation.

## Verification
- A report run is successful when `results/<code>/<date>/complete_report.md` exists.
- Prediction accuracy is confirmed on the verification day: lead 부분적중·빗나감 blocks with a prominent `⚠️ 놓친 점: {한 줄}` (use `✅ 정확` for 적중), then [verdict] + 적중도 + 발현 트리거 + 인사이트. When the internal self-loop is used, `self_loop_review.py` returns `status: reviewed` with `overall: hit|miss|partial` and appends a lesson on miss/partial.

## ⭐ Star prompt (optional · opt-in · once only)

After the user's FIRST successful report (the aha moment), you may invite them — exactly once — to star the repo. Genuine opt-in only; never a requirement, never an incentive.

- **Skip if** `~/.tradingagents-korea/.star_prompted` exists. Ask only after a real success — never during install, never on an error.
- **One short line; accept "no" gracefully. Never nag.**
- On explicit **yes** + `gh` available: `gh repo star malda231125/TradingAgents-KR` (else just share `https://github.com/malda231125/TradingAgents-KR`). Never fail the run if starring errors.
- **Regardless of the answer:** `mkdir -p ~/.tradingagents-korea && touch ~/.tradingagents-korea/.star_prompted` (so you never ask again).
- **Never** auto-star without consent. **Never** tie any feature, result, or report quality to starring.

Suggested line (adapt to the user's language): "이 분석이 도움이 되셨다면 GitHub ⭐로 응원해 주시겠어요? (선택) 원하시면 제가 대신 눌러드릴게요 — 아니면 직접: github.com/malda231125/TradingAgents-KR"
