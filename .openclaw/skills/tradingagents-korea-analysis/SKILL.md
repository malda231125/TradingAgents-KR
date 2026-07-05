---
name: tradingagents-korea-analysis
description: "Run TradingAgents-KR for Korean/KRX stocks only. Use for 국내주식, 한국 주식, 코스피, 코스닥, KRX, 6-digit Korean stock codes like 005930, or Korean company names with 국내/한국 wording such as 삼성전자 국내 주식, 하이닉스 국내주식, 현대차 한국 주식. Do not use for US/overseas tickers like AAPL, TSLA, NVDA, SPCX, NASDAQ/NYSE, or 해외/미국 주식 requests such as 애플 해외 주식/구글 해외 주식; use tradingagents-us-analysis instead. Also fact-check Korea TradingAgents Notion reports."
allowed-tools:
  - exec
  - process
---

# TradingAgents Korea Analysis

Use this skill when the user asks to analyze a **Korean/KRX stock** using the local `malda231125/TradingAgents-KR` repo and wants the long result as a Notion page.

## Routing boundary

- Use this skill for Korean/KRX stocks only:
  - 6-digit Korean stock codes such as `005930`, `000660`
  - Korean company names such as 삼성전자, SK하이닉스, 현대차
  - requests mentioning 국내주식, 한국 주식, 코스피, 코스닥, KRX
  - common phrasing:
    - 삼성전자 국내 주식 분석해줘 → Korea
    - 하이닉스 국내주식 분석해줘 → Korea
    - 현대차 한국 주식 분석해줘 → Korea
- Do **not** use this skill for US/overseas stocks:
  - tickers such as `AAPL`, `TSLA`, `NVDA`, `SPCX`
  - requests mentioning 미국 주식, 해외 주식, NASDAQ, NYSE, US stock
  - Korean names of overseas companies with 해외/미국 wording:
    - 애플 해외 주식 분석해줘 → US
    - 구글 해외 주식 분석해줘 → US
    - 테슬라 미국 주식 분석해줘 → US
  - use `tradingagents-us-analysis` instead
- If the user only says “주식 분석” and the market is ambiguous, infer from ticker format first. Ask one concise market-clarifying question only if the ticker/name cannot be classified.
- See `references/routing.md` for the Korea/US decision table.

## What it does

- Resolves a Korean stock name/code from the request.
- Runs this repository’s self-loop workflow on the checked-out repo branch, normally `main`.
- Uses the repo `.venv`, `.env`, and Codex CLI auth already configured in the OpenClaw container.
- Must use the full TradingAgents workflow, not a one-shot replacement, unless the user explicitly asks for a quick packet-only draft.
- Must use a subscription CLI provider, not direct OpenAI API-key execution.
- Default production runs use Codex CLI. For Claude A/B or explicit user requests, use `--llm-provider claude-cli --quick-model sonnet --deep-model opus-4.8 --cli-effort max`.
- Before generating a new self-loop report, the wrapper automatically runs the daily Key Risk Trigger check against the same self-loop base directory. Do not create a separate scheduled trigger-check job unless the user explicitly asks for an independent audit run.
- Publishes the self-loop report to Notion, including the latest decision record, digest, and prior retrospective when available.
- Surfaces concrete up/down Key Risk Triggers and a `🎯 Key Risk Trigger 일치` line when reporting trigger verification results.
- Returns the Notion URL and a short summary.
- Can also read a prior Notion report URL and fact-check the report's predicted signals against later actual market data.

## Final message format

For user-visible Telegram/chat reports, never send operations-log style summaries.
Do not list `SUCCESS`, local report paths, decision/digest/retrospective paths,
JSON paths, or raw execution artifacts in the final visible message unless the user
explicitly asks for debugging details.

This is a global project: write the final visible message in the language set by
`TRADINGAGENTS_REPORT_LANGUAGE` in the repo `.env` (default `ko`) — `ko` Korean,
`en` English, `ja` Japanese, `zh` Chinese (Simplified). The Notion report is
localized by the same var, so keep the chat summary in the same language.
**Write natively, never literally** — compose the narrative directly in the target
language's financial register; do not translate the Korean word-for-word (a stiff
literal translation is a failure). Never translate tickers / proper nouns. Use a
polished watchlist narrative — Korean by default (below), or the matching variant
(English / Japanese / Chinese) that follows:

```text
📑 <YYYY-MM-DD> 국내 워치리스트 분석 [<M/D> 장시작|장마감]

대표님, <시장 세션 설명> 기준으로 <종목명>(<code>)를 분석했습니다. 핵심 결론은 _<최종 판단>_입니다.

✅ <종목명> (<code>) — <가격/등락/거래량/수급 핵심>, <방향성 한 줄>
• [<세션> 분석 <기준가> 기준 <변동률/판정>] → [<매수/보류/매도/분할진입 등>] <근거 1~2문장. 숫자, 수급, 핵심 레벨 포함>
🎯 트리거 일치: <Key Risk Trigger 발현/미발현/첫 실행 N/A>. 발현 또는 미발현 근거를 구체 레벨로 설명.
• 인사이트: <다음 의사결정에 남길 한 문장>

🔁 self-loop <종목명>: <reviewed|pending|first_run|skipped> (<핵심 사유 또는 review_due>)

⚠️ 대기·주의 <n>건
• <다음 확인 일정, 데이터 caveat, 휴장/거래량/소스 불일치 등. 없으면 `없음`.>

🔗 Notion: <url>
```

For verification/fact-check reports, use the same structure but title it as
`국내 워치리스트 검증`, mark each thesis as `적중/부분적중/빗나감`, and make
`🎯 트리거 일치` the basis for the verdict. The only link that should be added
to these visible summaries is the Notion link.

English variant (when `TRADINGAGENTS_REPORT_LANGUAGE` = `en`) — same structure, polite English, address the user as "you":

```text
📑 <YYYY-MM-DD> KR watchlist analysis [<M/D> open|close]

Analyzed <stock>(<code>) for the <market session>. Bottom line: _<final call>_.

✅ <stock> (<code>) — <price/change/volume/flow core>, <one-line direction>
• [<session> analysis vs <ref price>: <change/verdict>] → [<Buy/Hold/Sell/scale-in>] <1–2 sentence rationale with levels, flow, key numbers>
🎯 Trigger match: <fired / not triggered / first run N/A>. Explain the (non-)trigger with concrete levels.
• Insight: <one sentence to carry into the next decision>

🔁 self-loop <stock>: <reviewed|pending|first_run|skipped> (<reason or review_due>)

⚠️ Watch / caveats <n>
• <next check schedule, data caveats, holiday/volume/source mismatch; "none" if none>

🔗 Notion: <url>
```

For a verification/fact-check report in English, title it `KR watchlist verification`, mark each thesis `Hit/Partial/Miss`, and make `🎯 Trigger match` the basis for the verdict.

日本語版（`TRADINGAGENTS_REPORT_LANGUAGE` = `ja`）— 同じ構成、自然な日本語（です・ます調、証券レポートの語彙）で。直訳しないこと：

```text
📑 <YYYY-MM-DD> 韓国株ウォッチリスト分析 [<M/D> 寄り付き|大引け]

<市場セッションの説明>を踏まえ、<銘柄>（<code>）を分析しました。結論は _<最終判断>_ です。

✅ <銘柄>（<code>）— <株価・騰落・出来高・需給の要点>、<方向感を一言>
• [<セッション>分析 <基準値>比 <変動率／判定>] → [<買い/様子見/売り/分割エントリー等>] <根拠1〜2文。数値・需給・重要レベルを含める>
🎯 トリガー一致: <キーリスクトリガー 発現／未達／初回N/A>。発現・未達の根拠を具体的な水準で説明。
• インサイト: <次の判断に残す一言>

🔁 self-loop <銘柄>: <reviewed|pending|first_run|skipped>（<主因 or review_due>）

⚠️ 保留・注意 <n>件
• <次の確認予定、データの注意点、休場／出来高／ソース不一致など。なければ「なし」>

🔗 Notion: <url>
```

中文版（`TRADINGAGENTS_REPORT_LANGUAGE` = `zh`）— 结构一致，用自然的中文（简体、券商研报术语）撰写，切勿逐字直译：

```text
📑 <YYYY-MM-DD> 韩股观察名单分析 [<M/D> 开盘|收盘]

结合<市场时段说明>，对<个股>（<code>）进行了分析。核心结论：_<最终判断>_。

✅ <个股>（<code>）— <价格/涨跌/成交量/资金面要点>，<方向判断一句话>
• [<时段>分析 相对<基准价>: <涨跌幅/判定>] → [<买入/观望/卖出/分批建仓等>] <1-2句理由，含点位、资金面、关键数据>
🎯 触发一致: <关键风险触发 已触发/未触发/首次N/A>。用具体点位说明（未）触发的依据。
• 洞察: <留给下次决策的一句话>

🔁 self-loop <个股>: <reviewed|pending|first_run|skipped>（<主因 或 review_due>）

⚠️ 待观察·注意 <n>项
• <下次确认时间、数据注意点、休市/成交量/数据源不一致等；若无则「无」>

🔗 Notion: <url>
```

For a Japanese verification report title it `韓国株ウォッチリスト検証`（的中/一部的中/外れ）; for Chinese use `韩股观察名单验证`（命中/部分命中/落空）.

## Analysis command

```bash
python3 .openclaw/skills/tradingagents-korea-analysis/scripts/run_analysis_to_notion.py --query "삼성전자 오늘 주식 분석해줘"
```

Useful options:

- `--ticker 005930` for explicit code.
- `--date YYYY-MM-DD`; default is today in Asia/Seoul.
- `--timeout 7200`; full high-quality Codex runs can take a long time. Do not stop early just because there is no output.
- `--dry-run` to validate parsing/report conversion without creating Notion page.
- `--skip-run --report-path <md>` to publish an existing report.
- `--legacy-single-run` only for emergency fallback to the old `main.py` single-shot report path.

## Fact-check command

Use when the user gives a TradingAgents Notion report URL and asks whether the prior report was right.

```bash
python3 .openclaw/skills/tradingagents-korea-analysis/scripts/factcheck_notion_report.py \
  --url "<notion-report-url>" \
  --publish
```

Useful options:

- `--check-date YYYY-MM-DD`; default is the next weekday after the report date, capped at today KST.
- `--ticker 005930` or `--report-date YYYY-MM-DD` if metadata parsing fails.
- omit `--publish` to return the fact-check Markdown directly instead of creating a Notion page.

## Daily trigger check command

The normal `run_analysis_to_notion.py` wrapper runs this automatically before each
new self-loop report. Use this command manually only when the user asks whether prior
key risk triggers or prediction checks have occurred without requesting a fresh full
analysis. It checks every unresolved decision record, not only records whose
`review_due` has arrived: if a Key Risk Trigger fired early, it immediately runs the
self-loop review, marks the record resolved, and appends the lesson; otherwise it
leaves the record pending and records `fired/not_fired/uncertain` in the digest.

```bash
python3 scripts/check_self_loop_triggers.py \
  --base-dir results/_self_loop \
  --as-of-date YYYY-MM-DD
```

Useful options:

- `--ticker 005930` to check only one ticker.
- `--no-ai-review` to use deterministic price-direction fallback only.

## Event-driven trigger review command

Use when a Key Risk Trigger is judged to have fired before the normal review horizon. This immediately scores the prior thesis, appends the lesson, and marks the decision record resolved so it is not reviewed twice.

```bash
python3 scripts/self_loop_review.py 005930 YYYY-MM-DD \
  --base-dir results/_self_loop \
  --trigger-fired
```

## Required runtime policy for new analysis

- Always run the full self-loop workflow for formal reports. The self-loop delegates to `TradingAgentsGraph`, saves a structured decision record, and checks the prior record when one exists.
- Use Codex CLI provider by default. Do not switch to direct `openai` provider just because an API key is missing.
- Claude CLI is allowed only when explicitly requested or for A/B checks: `--llm-provider claude-cli --quick-model sonnet --deep-model opus-4.8 --cli-effort max`.
- Prefer `gpt-5.5` for both quick and deep models when the repo supports those settings.
- Use maximum Codex reasoning effort. Current Codex CLI max is `xhigh`; `max` is invalid.
- Use long timeouts and wait for completion. `xhigh` full workflows may be silent for many minutes.
- Do not replace the full workflow with a packet-only one-shot report unless the user explicitly asks for a quick draft or approves the downgrade.
- If the final wrapper crashes after workflow completion due to serialization/report-export issues, recover the formal state log/checkpoint and publish that. This is allowed because the full workflow already ran.
- Do not use `--legacy-single-run` unless explicitly needed to diagnose or bypass a self-loop failure.

## Workflow

1. Acknowledge the requested stock/date or report URL and explain it may take a long time.
2. For new analysis, run `run_analysis_to_notion.py` with a long timeout. It runs the daily trigger check first, then the self-loop analysis by default.
3. For fact-checking, run `factcheck_notion_report.py` with the Notion URL.
4. For manual daily trigger checks, run `scripts/check_self_loop_triggers.py` against the same self-loop base directory.
5. Trigger checks must run even before `review_due`; report `🎯 트리거 일치` as `발현/미발현/불확실`. If the checker reports `trigger_fired=true`, surface the resulting retrospective and any `⚠️ 놓친 점`.
6. If the run is long, keep it in background and check with `process`; do not kill solely due to silence.
7. On success, return the final message using the `Final message format` above:
   - cite the ticker/date/session in the title
   - summarize the actual decision with concrete price, level, volume, and investor-flow evidence
   - include `🎯 트리거 일치`, one insight, self-loop status, caution items, and the Notion URL
   - keep local paths and artifact IDs out of the visible message unless explicitly requested

## Caveats

- This is analysis, not investment advice.
- Do not execute trades from this skill.
- If Codex auth fails, run `codex login --device-auth` in the repo container and retry.
- Do not publish a report that was generated by a non-formal one-shot fallback as if it were a full TradingAgents report.
- If ticker resolution fails, ask for the 6-digit Korean stock code.
- Fact-checking compares report claims against market/technical packets; it is not a full realized P&L backtest unless the report included explicit entry/exit prices.
- The Notion parent page comes from `TRADINGAGENTS_NOTION_PAGE_ID` in `.env` (there is no built-in default); the runner errors if it is unset. Pass `--parent-page-id` to override per run.
