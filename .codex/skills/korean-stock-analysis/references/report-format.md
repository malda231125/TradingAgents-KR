# 📐 Slack/Telegram 보고 포맷 (single source)

All summary/verification reports use this style (Slack mrkdwn; Telegram renders the same plain layout). Keep it consistent across agents.

- **굵게는 별표 1개** `*텍스트*`. `#` 헤딩·표(table) 금지. 항목은 불릿으로 위→아래 나열.
- **첫 줄 = 한 줄 제목**: `📑 {날짜} {대상} [{세션}]`.
- **종목별 블록**: `*{종목명} ({code})* — 한 줄 요지` 다음, 불릿으로:
  - `🎯 Key Risk Trigger 일치` **(필수 라인)**: 발현한 트리거 레벨+방향, 또는 `미발현(어느 레벨도 안 건드림/중간구간)`. 검증 보고면 이 줄이 적중/빗나감 판정 근거이자 self-loop 회고(🔁)로 이어진다.
  - `[의견: 매수/매도/보류]`
  - 상승 트리거(구체 레벨) · 하락 트리거(구체 레벨) · 특이점
- **상태 마커**: 적중 `✅` · 부분적중·빗나감 `⚠️`(놓친 점을 블록 맨 앞 줄에 굵게) · self-loop `🔁` · 정상·결론 `🟢` · 경고·지연 `⚠️`.
- 이모지는 블록당 1~2개로 절제. **존댓말 + '사용자' 호칭.**
- 첨부는 마지막에 `MEDIA:<절대경로>` 줄(평문, 마크다운 래핑 금지, 각각 자체 줄). `MEDIA:` 줄이 파일을 실제로 업로드한다 — 경로만 붙여넣지 말 것.

## 예시 템플릿 (그대로 따라 쓸 것)

```
📑 2026-06-24 국내 워치리스트 [장마감]

*삼성전자 (005930)* — 종가 *340,500* (+9.84%)
• 🎯 Key Risk Trigger 일치: 미발현 — 상승(362,500 종가 돌파) ✗ · 하락(310,000 종가 하회) ✗ → 중간구간
• [의견: 보류·관망] 보유 유지·신규 추격 보류
• 🔺상승: 362,500 거래량 동반 종가 돌파 / 외국인 순매수 복귀
• 🔻하락: 310,000 종가 하회 → 비중축소
• 특이: +9.84% 반등은 자사주發, 돌파 게이트 밖

🟢 결론: 보류·관망. 검증일 2026-06-25.
MEDIA:/abs/path/results/005930/2026-06-24/complete_report.md
```

검증 보고면 종목 블록 맨 앞에 적중 `✅ 정확` / 부분·빗나감 `⚠️ 놓친 점: …` 을 굵게 먼저, 끝에 `🔁 self-loop {종목}: {status}` 한 줄.

## English variant (when `TRADINGAGENTS_REPORT_LANGUAGE` = `en`)

Same layout, markers, and emoji discipline; write prose in polite English (address the user as "you") and translate the fixed labels:

- 간단한 요약 → Summary · 상승 체크포인트 → Upside checkpoints · 하락 체크포인트 → Downside checkpoints
- `🎯 Key Risk Trigger 일치` → `🎯 Key Risk Trigger match` · 미발현(중간구간) → not triggered (mid-range)
- `[의견: 매수/매도/보류]` → `[View: Buy / Sell / Hold]` · 특이 → Note · 결론 → Conclusion · 검증일 → Verify date
- 적중 / 부분적중 / 빗나감 → Hit / Partial / Miss · `✅ 정확` → `✅ Accurate` · `⚠️ 놓친 점` → `⚠️ Missed`
- 발현 트리거 → Fired triggers · 틀린 부분 → What missed · 인사이트 → Insight · [장마감] → [close] · 국내 워치리스트 → KR watchlist

```
📑 2026-06-24 KR watchlist [close]

*Samsung Electronics (005930)* — close *340,500* (+9.84%)
• 🎯 Key Risk Trigger match: not triggered — upside (close above 362,500) ✗ · downside (close below 310,000) ✗ → mid-range
• [View: Hold] keep the position, hold off on new entries
• 🔺Upside: close above 362,500 on volume / foreign net-buying returns
• 🔻Downside: close below 310,000 → reduce
• Note: the +9.84% bounce is buyback-driven, outside the breakout gate

🟢 Conclusion: Hold. Verify date 2026-06-25.
MEDIA:/abs/path/results/005930/2026-06-24/complete_report.md
```

For a verification report, lead the stock block with `✅ Accurate` or `⚠️ Missed: …`, then `[View: …]` + Hit/Partial/Miss + Fired triggers + Insight, and end with `🔁 self-loop {stock}: {status}`.

## 日本語版（`TRADINGAGENTS_REPORT_LANGUAGE` = `ja` のとき）

**直訳は禁止。** 韓国語をなぞらず、日本語の金融レポートとして自然な文体（です・ます調、証券レポートの語彙）で最初から書き起こすこと。レイアウト・マーカー・絵文字の使い方は共通。ラベル対応：上値チェックポイント／下値チェックポイント・`🎯 キーリスクトリガー`・未達（レンジ内）・`[判断: 買い/売り/様子見]`・注目・結論・検証日・的中/一部的中/外れ・`✅ 的中`・`⚠️ 見落とし`・発現トリガー・外した点・インサイト・[大引け]／[寄り付き]・ウォッチリスト。

```
📑 2026-06-24 韓国株ウォッチリスト [大引け]

*サムスン電子 (005930)* — 終値 *340,500*（+9.84%）
• 🎯 キーリスクトリガー: 未達 — 上値（362,500の終値ブレイク）✗ ・下値（310,000の終値割れ）✗ → レンジ内
• [判断: 様子見] 保有は継続、新規の追随は見送り
• 🔺上値: 出来高を伴う362,500の終値ブレイク／外国人の買い越し復帰
• 🔻下値: 310,000の終値割れ → 比重縮小
• 注目: +9.84%の反発は自社株買い主導で、ブレイクの条件は満たさず

🟢 結論: 様子見。検証日は2026-06-25。
MEDIA:/abs/path/results/005930/2026-06-24/complete_report.md
```

検証レポートでは冒頭に `✅ 的中` か `⚠️ 見落とし: …` を置き、`[判断: …]`＋的中/一部的中/外れ＋発現トリガー＋インサイト、最後に `🔁 self-loop {銘柄}: {status}`。

## 中文版（当 `TRADINGAGENTS_REPORT_LANGUAGE` = `zh`）

**禁止逐字直译。** 不要照搬韩文语序，要用中文财经报告的自然表达（简体、券商研报术语）重新撰写。版式、标记、表情符号保持一致。标签对应：上行检查点／下行检查点・`🎯 关键风险触发`・未触发（区间内）・`[观点: 买入/卖出/观望]`・备注・结论・验证日・命中/部分命中/落空・`✅ 命中`・`⚠️ 遗漏`・已触发条件・判断偏差・洞察・[收盘]／[开盘]・观察名单。

```
📑 2026-06-24 韩股观察名单 [收盘]

*三星电子 (005930)* — 收盘 *340,500*（+9.84%）
• 🎯 关键风险触发: 未触发 — 上行（收盘突破362,500）✗ · 下行（收盘跌破310,000）✗ → 区间内
• [观点: 观望] 维持持仓，暂不追高
• 🔺上行: 放量收盘突破362,500 / 外资转为净买入
• 🔻下行: 收盘跌破310,000 → 减仓
• 备注: +9.84%的反弹由回购推动，尚未站稳突破位

🟢 结论: 观望。验证日为2026-06-25。
MEDIA:/abs/path/results/005930/2026-06-24/complete_report.md
```

验证报告在每只个股块首行标注 `✅ 命中` 或 `⚠️ 遗漏: …`，随后 `[观点: …]`＋命中/部分命中/落空＋已触发条件＋洞察，末行 `🔁 self-loop {个股}: {status}`。
