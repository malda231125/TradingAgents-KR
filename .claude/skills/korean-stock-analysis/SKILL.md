---
name: korean-stock-analysis
description: "On-demand Korean (KRX) stock analysis via TradingAgents-KR. Trigger on '{종목명} 국내 주식 분석해줘' (국내주식/한국주식/코스피/코스닥/KRX/6-digit codes like 005930). Runs the multi-agent analysis, posts a Slack/Telegram summary in the 📐 report format (up/down Key Risk Triggers + 🎯 trigger-match line), attaches the report .md, logs the trend to 국내주식.md, and verifies the prediction on the next trading day."
allowed-tools: Bash, Read, Write, Edit, WebSearch
---

# Korean Stock Analysis (Claude Code Skill)

When the owner says **"{종목명} 국내 주식 분석해줘"** (or 국내주식/한국 주식/코스피/코스닥/KRX, or a 6-digit code like `005930`), run this end-to-end. Always report a short plan + ETA first (owner rule), then execute.

Do **not** use this for US/overseas tickers (AAPL, TSLA, NVDA, 해외/미국 주식).

## Language (기본 한국어 · language-driven)
This is a global project. All user-facing output — the Slack/Telegram summary, checkpoint labels, the `국내주식.md` ledger, and verification wording — follows `TRADINGAGENTS_REPORT_LANGUAGE` in the repo `.env` (default `ko`). Read it before reporting:
- `ko` (default) → Korean · `en` → English · `ja` → Japanese · `zh` → Chinese (Simplified). Use the matching variant of the 📐 format below. The chat summary and the report share this language.
- **Write natively, never literally.** Compose the summary directly in the target language's own financial register — do **not** translate the Korean/English word-for-word. Localize idioms, sentence flow, politeness level, and market terminology so a native reader finds it natural (a stiff literal translation is a failure). The example templates are style references, not fill-in-the-blank strings.
`main.py` already localizes `complete_report.md` from the same var, so the attached report and your summary share one language. Never translate tickers / proper nouns.

## Fixed facts
- Repo: `TradingAgents-KR` (Claude CLI backend, Opus 4.8, effort=max via `.env`; quick=sonnet/deep=opus-4.8).
- Repo path resolves from `$TRADINGAGENTS_KOREA_REPO` **if it is exported in the shell environment**; otherwise the bundled scripts auto-detect the repo root by walking up from their own location (works from any checkout path). Setting the var only in `.env` does **not** reach these shell scripts — `.env` is loaded inside `main.py`, after the script has already resolved the path — so export it in the environment if you need to override.
- Runner: `${CLAUDE_SKILL_DIR}/scripts/analyze_kr_stock.sh <code> <yyyy-mm-dd>` (detached-safe; writes sentinels). The data pre-flight lives **inside** `main.py` (reuses the cached market packet, no extra API call) and aborts with `DATA_UNAVAILABLE` when KIS returns empty data — no separate pre-flight step needed.
- Output: `results/<code>/<date>/complete_report.md` (under the repo).
- Trend ledger: `국내주식.md`. Trading-day calendar: `${CLAUDE_SKILL_DIR}/scripts/kr_is_open.py <date> [check|next]`.
- `${CLAUDE_SKILL_DIR}` resolves to this skill's folder (`.claude/skills/korean-stock-analysis/`) regardless of cwd; the bundled scripts resolve the repo root themselves (auto-detect, or `$TRADINGAGENTS_KOREA_REPO`) and `cd` into it.
- A full run with Opus + effort max takes ~20–40 min.

## Steps

1. **Resolve the ticker.** Convert 종목명 → 6-digit KRX code (삼성전자=005930, SK하이닉스=000660, …). If unsure, `web_search "{종목명} 종목코드"` and confirm it is a 6-digit number. If still ambiguous, ask the owner.

2. **Announce.** Post a top-level message exactly `{yyyy-mm-dd} {종목명}` (today's KST date). Deliver the rest as a thread reply / follow-up.

3. **Launch**:
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/analyze_kr_stock.sh" <code> <date>
   ```
   For a Unix detached run, use:
   ```bash
   nohup bash "${CLAUDE_SKILL_DIR}/scripts/analyze_kr_stock.sh" <code> <date> </dev/null >/dev/null 2>&1 &
   ```
   Then watch for completion with a persistent poll on the sentinel:
   `while [ ! -f results/.DONE_<code> ] && [ ! -f results/.FAIL_<code> ]; do sleep 20; done` then report the outcome. (If the monitor dies when a new message arrives, just re-check the sentinel next turn.)

4. **Deliver** in the 📐 report format (below):
   - 간단한 요약 (final rating + 1-line thesis) — in the language set by `TRADINGAGENTS_REPORT_LANGUAGE` (Korean by default, English when `en`).
   - **상승 체크포인트 / 하락 체크포인트** — the heart of the report. **Pull concrete levels and named catalysts verbatim from the report's "Key Risk Triggers / 핵심 리스크 트리거 / 무효화·격상·격하 조건" (Portfolio Manager) section.** e.g. "MA20 324,875 종가 이탈", "거래량 20일평균 0.8~1배 회복 + 신고가 재돌파", "외국인 순매도 전환", "52주 저점 159,400 이탈". **NO generic/뻔한 문구.**
   - The report's top-line `Final signal` is a regex-extracted label that often disagrees with the body — **do not trust it; use the body conclusion** (투자의견/실행/Key Risk sections). Reason it out; no keyword matching (owner rule).
   - **ATTACH the full report as a file — never just paste the path.** Emit on its OWN line, plain text, no markdown wrapper (this uploads the file):
     `MEDIA:<repo-abs-path>/results/<code>/<date>/complete_report.md`
     A bare path the owner cannot download; the `MEDIA:` line is what attaches it.

5. **Log to the trend ledger** `국내주식.md` — append a block (schema below) with a verification line marked `[PENDING — 검증일: <next trading day>]`. Next trading day = `${CLAUDE_SKILL_DIR}/scripts/kr_is_open.py <date> next`.

6. **Ensure verification.** A daily verify job (after close, ~16:00 KST) scores each PENDING entry whose 검증일 ≤ today. It should already exist; if missing, create it.

## 국내주식.md entry schema
```
## {YYYY-MM-DD} {종목명} ({code})
- 분석일 종가: {price or N/A}
- 예측 바이어스: {상승 / 하락 / 중립(편향 표기)}
- 상승 체크포인트(Key Risk Trigger 레벨): {…}
- 하락 체크포인트(Key Risk Trigger 레벨): {…}
- 검증 [PENDING — 검증일: {next trading day}]
```

When `TRADINGAGENTS_REPORT_LANGUAGE` is `en`/`ja`/`zh`, keep the same file (`국내주식.md`) but write the entry natively in the selected language. For English, use labels such as `Analysis-day close` / `Predicted bias {up/down/neutral}` / `Upside checkpoints (Key Risk Trigger levels)` / `Downside checkpoints` / `Verify [PENDING — verify date: {next trading day}]`; for Japanese/Chinese, use the localized labels in the report-format section.

## Verification (run after close, or manually)
The point is **not just 적중/빗나감 — translate the outcome into an actionable [매수/매도/보류·관망] opinion, and on 부분적중 say which part was wrong**, so the owner learns. For each entry whose 검증일 ≤ today and still PENDING:
1. Get the 검증일 close (KIS, or `web_search "{종목명} {검증일} 종가"`); compute the move vs 분석일 종가.
2. Reason (no regex) which 상승(매수)/하락(매도) Key Risk Triggers actually fired.
3. **Action verdict**: fired triggers lean up/breakout → **[매수]**; lean down/invalidation/de-risk → **[매도]**; neither met / 고가 거부·박스권·되밀림 → **[보류·관망]**.
4. **적중도**: original bias/triggers vs reality → 적중 / 부분적중 / 빗나감.
5. Replace the PENDING line with:
   `- 검증 [{검증일}]: 종가 {price} ({±x.x%}) → [{매수/매도/보류·관망}] {적중/부분적중/빗나감}. 발현 트리거: {what fired}. 틀린 부분: {what missed; "없음" if 적중}. 인사이트: {one-line lesson}`
6. Post the verdict (per-stock). **When 부분적중 or 빗나감, LEAD that stock's block with a prominent first line `⚠️ 놓친 점: {한 줄}`** so the miss is immediately visible (for 적중 use `✅ 정확`). Then [verdict] + 적중도 + 발현 트리거 + 인사이트.

## 📐 Slack/Telegram 보고 포맷 (공통 — 다른 에이전트가 써도 일관되게)

- **굵게는 별표 1개** `*텍스트*`. `#` 헤딩·표(table) 금지. 항목은 불릿으로 위→아래 나열.
- **첫 줄 = 한 줄 제목**: `📑 {날짜} {대상} [{세션}]`.
- **종목별 블록**: `*{종목명} ({code})* — 한 줄 요지` 다음, 불릿으로:
  - `🎯 Key Risk Trigger 일치` **(필수 라인)**: 발현한 트리거 레벨+방향, 또는 `미발현(어느 레벨도 안 건드림/중간구간)`. 검증 보고면 이 줄이 적중/빗나감 판정 근거이자 self-loop 회고(🔁)로 이어진다.
  - `[의견: 매수/매도/보류]`
  - 상승 트리거(구체 레벨) · 하락 트리거(구체 레벨) · 특이점
- **상태 마커**: 적중 `✅` · 부분적중·빗나감 `⚠️`(놓친 점을 블록 맨 앞 줄에 굵게) · self-loop `🔁` · 정상·결론 `🟢` · 경고·지연 `⚠️`.
- 이모지는 블록당 1~2개로 절제. **한국어면 존댓말 + '사용자' 호칭; 영어면 polite tone + address the user as "you".**
- 첨부는 마지막에 `MEDIA:<절대경로>` 줄(평문, 마크다운 래핑 금지, 각각 자체 줄).

### 예시 템플릿 (그대로 따라 쓸 것)

📑 2026-06-24 국내 워치리스트 [장마감]

*삼성전자 (005930)* — 종가 *340,500* (+9.84%)
• 🎯 Key Risk Trigger 일치: 미발현 — 상승(362,500 종가 돌파) ✗ · 하락(310,000 종가 하회) ✗ → 중간구간
• [의견: 보류·관망] 보유 유지·신규 추격 보류
• 🔺상승: 362,500 거래량 동반 종가 돌파 / 외국인 순매수 복귀
• 🔻하락: 310,000 종가 하회 → 비중축소
• 특이: +9.84% 반등은 자사주發, 돌파 게이트 밖

🟢 결론: 보류·관망. 검증일 2026-06-25.
MEDIA:<repo-abs-path>/results/005930/2026-06-24/complete_report.md

— 검증 보고면 종목 블록 맨 앞에 적중 `✅ 정확` / 부분·빗나감 `⚠️ 놓친 점: …` 을 굵게 먼저, 끝에 `🔁 self-loop {종목}: {status}` 한 줄.

### English variant (when `TRADINGAGENTS_REPORT_LANGUAGE` = `en`)

Same layout, markers, and emoji discipline; write prose in polite English (address the user as "you") and translate the fixed labels:

- 간단한 요약 → Summary · 상승 → Upside · 하락 → Downside
- `🎯 Key Risk Trigger 일치` → `🎯 Key Risk Trigger match` · 미발현(중간구간) → not triggered (mid-range)
- `[의견: 매수/매도/보류]` → `[View: Buy / Sell / Hold]` · 특이 → Note · 결론 → Conclusion · 검증일 → Verify date
- 적중 / 부분적중 / 빗나감 → Hit / Partial / Miss · `✅ 정확` → `✅ Accurate` · `⚠️ 놓친 점` → `⚠️ Missed` · [장마감] → [close] · 국내 워치리스트 → KR watchlist

```
📑 2026-06-24 KR watchlist [close]

*Samsung Electronics (005930)* — close *340,500* (+9.84%)
• 🎯 Key Risk Trigger match: not triggered — upside (close above 362,500) ✗ · downside (close below 310,000) ✗ → mid-range
• [View: Hold] keep the position, hold off on new entries
• 🔺Upside: close above 362,500 on volume / foreign net-buying returns
• 🔻Downside: close below 310,000 → reduce
• Note: the +9.84% bounce is buyback-driven, outside the breakout gate

🟢 Conclusion: Hold. Verify date 2026-06-25.
MEDIA:<repo-abs-path>/results/005930/2026-06-24/complete_report.md
```

For a verification report, lead the stock block with `✅ Accurate` or `⚠️ Missed: …`, then `[View: …]` + Hit/Partial/Miss + Fired triggers + Insight, and end with `🔁 self-loop {stock}: {status}`.

### 日本語版 (`TRADINGAGENTS_REPORT_LANGUAGE` = `ja`)

**直訳は禁止。** 日本語の金融レポートとして自然な文体（です・ます調、証券レポートの語彙）で最初から書き起こす。ラベル：上値／下値・`🎯 キーリスクトリガー`・未達（レンジ内）・`[判断: 買い/売り/様子見]`・注目・結論・検証日・的中/一部的中/外れ・`✅ 的中`・`⚠️ 見落とし`・[大引け]／[寄り付き]。

```
📑 2026-06-24 韓国株ウォッチリスト [大引け]

*サムスン電子 (005930)* — 終値 *340,500*（+9.84%）
• 🎯 キーリスクトリガー: 未達 — 上値（362,500の終値ブレイク）✗ ・下値（310,000の終値割れ）✗ → レンジ内
• [判断: 様子見] 保有は継続、新規の追随は見送り
• 🔺上値: 出来高を伴う362,500の終値ブレイク／外国人の買い越し復帰
• 🔻下値: 310,000の終値割れ → 比重縮小
• 注目: +9.84%の反発は自社株買い主導で、ブレイクの条件は満たさず

🟢 結論: 様子見。検証日は2026-06-25。
MEDIA:<repo-abs-path>/results/005930/2026-06-24/complete_report.md
```

### 中文版 (`TRADINGAGENTS_REPORT_LANGUAGE` = `zh`)

**禁止逐字直译。** 用中文财经报告的自然表达（简体、券商研报术语）重新撰写。标签：上行／下行・`🎯 关键风险触发`・未触发（区间内）・`[观点: 买入/卖出/观望]`・备注・结论・验证日・命中/部分命中/落空・`✅ 命中`・`⚠️ 遗漏`・[收盘]／[开盘]。

```
📑 2026-06-24 韩股观察名单 [收盘]

*三星电子 (005930)* — 收盘 *340,500*（+9.84%）
• 🎯 关键风险触发: 未触发 — 上行（收盘突破362,500）✗ · 下行（收盘跌破310,000）✗ → 区间内
• [观点: 观望] 维持持仓，暂不追高
• 🔺上行: 放量收盘突破362,500 / 外资转为净买入
• 🔻下行: 收盘跌破310,000 → 减仓
• 备注: +9.84%的反弹由回购推动，尚未站稳突破位

🟢 结论: 观望。验证日为2026-06-25。
MEDIA:<repo-abs-path>/results/005930/2026-06-24/complete_report.md
```

## Bundled scripts (`scripts/`)
- `analyze_kr_stock.sh <code> <date>` — detached single-stock runner → `complete_report.md` + sentinels.
- `analyze_kr_watchlist.sh <date> [codes…]` — sequential multi-stock (watchlist) runner.
- `kr_is_open.py <date> [check|next]` — KRX trading-day calendar (KIS chk-holiday).
- `kr_preflight.py <code>` — standalone KIS data check (the runner relies on main.py's built-in pre-flight; use this only for ad-hoc checks).
- `kr_foreign_flow.py <code> [days]` — foreign/institutional net-buy streak.

## ⭐ Star prompt (optional · opt-in · once only)

After the user's FIRST successful report (the aha moment), you may invite them — exactly once — to star the repo. Genuine opt-in only; never a requirement, never an incentive.

- **Skip if** `~/.tradingagents-korea/.star_prompted` exists. Ask only after a real success — never during install, never on an error.
- **One short line; accept "no" gracefully. Never nag.**
- On explicit **yes** + `gh` available: `gh repo star malda231125/TradingAgents-KR` (else just share `https://github.com/malda231125/TradingAgents-KR`). Never fail the run if starring errors.
- **Regardless of the answer:** `mkdir -p ~/.tradingagents-korea && touch ~/.tradingagents-korea/.star_prompted` (so you never ask again).
- **Never** auto-star without consent. **Never** tie any feature, result, or report quality to starring.

Suggested line (adapt to the user's language): "이 분석이 도움이 되셨다면 GitHub ⭐로 응원해 주시겠어요? (선택) 원하시면 제가 대신 눌러드릴게요 — 아니면 직접: github.com/malda231125/TradingAgents-KR"
