<a name="readme-top"></a>

<div align="center">

# TradingAgents Korea 🇰🇷

**它不止于分析。它会记住、给自己打分，并且越来越少出错。**

一个韩国股票投研智能体：记录自己过去的判断，用 hit/miss 给自己打分，并在下一次修正自己的推理——在 KIS、DART、ECOS 和 Naver News 的**真实数据**上进行多智能体辩论，运行在你的 Claude Code / Codex 订阅之上。

[![Self-improving loop](https://img.shields.io/badge/Self--improving-loop-ff6b6b.svg)](#-核心差异化ai-投研自我改进闭环)
[![CI](https://github.com/malda231125/TradingAgents-KR/actions/workflows/ci.yml/badge.svg)](https://github.com/malda231125/TradingAgents-KR/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)
[![TradingAgents](https://img.shields.io/badge/Based%20on-TradingAgents-14C290.svg)](https://github.com/TauricResearch/TradingAgents)
[![Korea Market](https://img.shields.io/badge/Market-KRX%20%7C%20KOSPI%20%7C%20KOSDAQ-red.svg)](#为什么选择-tradingagents-korea)

[English](README.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [中文](README.zh.md)

</div>

---

> [!CAUTION]
> TradingAgents Korea 是开源的研究、教育和个人投研辅助项目。它不是投资建议、买卖推荐系统，也不是自动交易系统。所有投资判断和责任均由使用者自行承担。

## 这是什么？

TradingAgents Korea 是 [`TauricResearch/TradingAgents`](https://github.com/TauricResearch/TradingAgents) 面向韩国股票市场的本地化 fork。

原版 TradingAgents 提供了多智能体金融分析框架。本项目把这个框架接入韩国市场的数据、股票标识符和报告输出方式，重点服务 KOSPI/KOSDAQ 的深度研究场景。

- **KIS**：韩国股票价格、OHLCV、技术指标和结构化市场数据
- **DART**：公告、公司标识符和事件上下文
- **ECOS**：韩国银行宏观经济数据
- **Naver News**：韩语本地新闻
- **yfinance**：补充性的全球/外部视角
- **Claude Code / Codex CLI**：基于本地订阅/登录环境的 LLM 执行路径
- **Notion export**：可选的报告发布 helper

```text
分析三星电子
       ↓
005930 / DART corp code / Naver query / yfinance symbol 解析
       ↓
KIS + DART + ECOS + Naver News 数据预取
       ↓
市场 / 新闻 / 基本面 / 宏观 feature packet
       ↓
TradingAgents 多智能体辩论与风险审查
       ↓
Markdown / Notion 研究报告
```

> ⏱️ **生成一份完整报告平均可能需要 15 分钟以上**（以 GPT-5.5 或 Claude Opus 4.8 最大推理为准）。这是正常的——它是深度投研框架，而非快速摘要工具。**运行时间长并不代表出了问题。**

## ❓ 为什么不直接问 ChatGPT「三星电子怎么样」？

AI 选股分析最糟糕的地方，就是**写出一份看起来很像样的报告，然后就结束了。**

今天分析「三星看起来不错」，到了明天它连这个判断都不记得。没有人去核对它到底对没对，下一次分析又从一张白纸重新开始。

所以我们做了这个项目。**TradingAgents Korea 的核心不是一次性的 AI 选股分析。**

> **每日分析 → 记录预测 → 次日验证 → 错了就复盘 → 反馈进下一次分析**

这个 **AI 投研自我改进闭环**才是重点。

| 直接问 AI | TradingAgents Korea |
|---|---|
| 每次从零开始，不记得过去的判断 | 记录每次判断，并在下一次运行时**复盘** |
| 从来没人给它打分 | 用 **hit / miss / partial** 给自己打分 |
| 一句和稀泥的回答（「有风险，请谨慎」） | 市场·新闻·基本面·多空·风险**多智能体辩论** |
| 看似可信的假数字（幻觉） | **feature packet** 先把证据数据固定下来 |

## 🔄 核心差异化：AI 投研自我改进闭环

大多数 AI 分析工具止步于「分析 → 报告」。TradingAgents Korea 把后面的闭环补上。

```text
每日分析
   ↓
记录预测      decisions/YYYY-MM-DD/<ticker>.json      ← 结构化判断记录
   ↓
次日验证      将之前的 thesis 与证据 packet 对照
   ↓
错了就复盘    retrospectives/YYYY-MM-DD/<ticker>.md   → hit / miss / partial / uncertain
   ↓
反馈进下一次  lessons/<ticker>.jsonl                  → 注入下一次运行的 prompt
```

交互式 CLI 会**自动**运行这个闭环：每次运行都会找到该股票最近的判断记录、执行复盘、把得到的教训注入下一次分析，然后保存一条新的判断记录（首次运行会跳过复盘）。

```bash
# 单独运行自我改进闭环
.venv/bin/python scripts/run_self_loop.py --ticker 005930 --date YYYY-MM-DD
```

复盘判定（`hit` / `miss` / `partial` / `uncertain`）默认由订阅制 CLI LLM 审阅确定性证据 packet 后给出；可用 `--no-ai-review` 仅运行确定性回退逻辑。在长时间批量运行时，prompt 上下文会使用精简的 `lessons/<ticker>.summary.md` 摘要加上最近的教训，避免累积的教训淹没 prompt。

> 我们不吹嘘收益率。相反，我们**公开 AI 给自己过去判断打分的记录。**

## 为什么选择 TradingAgents Korea？

市面上有不少面向美股或全球股票的 AI 金融 agent，但韩国股票研究需要不同的数据源、解释框架和本地语境。

| 问题 | TradingAgents Korea 的做法 |
|---|---|
| 韩国股票可能写成 `005930`、`삼성전자` 或 `005930.KS` | 分离并保留不同数据源所需的标识符 |
| 仅靠 Yahoo Finance 可能不足以覆盖韩国市场数据 | 使用 KIS 作为韩国结构化市场数据核心 |
| 韩国上市公司公告应以 DART 为准 | 将 DART 公告和事件上下文作为独立层 |
| 韩国宏观环境需要 BOK/ECOS 语境 | 引入 ECOS 利率、汇率和宏观数据 |
| LLM 容易生成看似合理但未经校验的数字 | 先构建明确 feature packet，再进入推理 |
| 高级多智能体报告用按量 API 计费可能成本很高 | 通过 Claude Code / Codex CLI 订阅型 runtime 承载长时间报告生成 |
| 本地投资者需要韩语报告，全球开发者需要英文文档 | 英文/韩文/中文 README，并支持韩语报告输出 |

## 核心特点

- 🇰🇷 **韩国股票优先** — 支持 `005930`、`000660`、`삼성전자`、`SK하이닉스` 等输入
- 🧩 **多智能体投研流程** — 市场、新闻、基本面、多空辩论、交易计划、风险审查、组合经理判断
- 📡 **韩国数据栈** — KIS、DART、ECOS 和 Naver News 作为一等数据源
- 🧠 **CLI-first LLM 执行** — 通过 Claude Code / Codex CLI 跑长流程，避免把每个 agent 步骤都推给按量 API 计费
- 🧾 **高级报告优先** — 生成适合阅读和归档的长篇 Markdown 研究报告
- 🗂️ **Notion 发布 helper** — 可选的 OpenClaw 发布流程
- 🛡️ **公开发布安全文档** — 避免 API key、`.env`、Notion token 和本地路径泄露

## 为什么是 CLI-first？

高级多智能体投研非常消耗 token。

一次完整的 TradingAgents Korea 运行可能包含市场分析、新闻分析、基本面分析、多空辩论、交易计划、风险审查、组合经理判断和长篇 Markdown 报告。如果整个流程都通过按量计费的 LLM API 执行，成本会很快上升。

TradingAgents Korea 围绕 Claude Code 和 Codex CLI runtime 设计，让重推理路径可以运行在用户已有的本地 CLI 订阅/登录环境中，而不是让每一个 agent step 都产生 per-token API 费用。

这并不意味着完全不需要外部凭证。KIS、Naver、DART、ECOS 等数据 API 仍然需要配置；CLI 使用也受各 provider 的订阅条款和使用限制约束。核心目标是让反复生成深度、高级投研报告在个人使用场景下更现实。

## 定位

这个仓库不只是数据连接器，也不只是 MCP tool server。

它的定位是 **面向韩国股票的多智能体投研框架**：

- FinanceDataReader 等数据库是有用的构件。
- MCP server 适合把工具暴露给 Claude/Cursor。
- TradingAgents Korea 关注端到端投研流程：数据预取 → 分析员角色 → 辩论 → 风险审查 → 最终报告。

一句话：

> 面向韩国股票的高级投研框架，优先为 Claude Code 和 Codex CLI 优化，而不是只做短小的 API 计费 demo。

## 快速开始

你不需要记住安装命令。

不是开发者也没关系，可以把安装交给 Claude Code 或 Codex。

先克隆仓库：

```bash
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
```

然后对 Claude Code 或 Codex 说：

```text
请读取 llm.txt，并在我的电脑上安装这个项目。请设置 Python 虚拟环境、安装依赖、创建 .env，并确认可以运行。
```

详细安装步骤已经写在 [llm.txt](llm.txt) 中。它是给 AI agent 看的安装指南，包含 Python 版本、虚拟环境、依赖安装、环境变量和运行确认。

安装完成后，可以直接这样请求：

```text
分析三星电子韩国股票。
分析 005930。
帮我生成 SK hynix 的韩国股票研究报告。
```

TradingAgents Korea 不是短摘要工具，而是面向高级长篇研究报告的框架。根据股票和数据状态，一次完整运行可能需要较长时间。

### 手动安装（不使用 agent）

如果你不使用 Claude Code / Codex，也可以自己安装。

**macOS / Linux / WSL**

```bash
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
cp .env.example .env          # 然后编辑 .env 填入你的 API key
.venv/bin/python main.py 005930
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/malda231125/TradingAgents-KR.git
cd TradingAgents-KR
py -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e .
copy .env.example .env         # 然后编辑 .env 填入你的 API key
.venv\Scripts\python main.py 005930
```

> 在 Debian/Ubuntu 上，如果 `python3 -m venv` 因 `ensurepip is not available` 失败，
> 请执行 `sudo apt install -y python3-venv` 后重试。

默认 LLM runtime 是 Codex CLI。如果你改用 Claude Code，请在 `.env` 中切换 runtime 配置块：

```bash
TRADINGAGENTS_LLM_PROVIDER=claude-cli
TRADINGAGENTS_QUICK_MODEL=sonnet
TRADINGAGENTS_DEEP_MODEL=opus
```

安装完成后，先运行预检：

```bash
.venv/bin/tradingagents doctor
```

该命令不会输出真实的 API key 值，只检查：

- 是否已安装 `codex` 或 `claude` CLI
- `.env` 中是否已填入推荐的 KIS / Naver / DART / ECOS key
- 对缺失项给出 README 和申请链接的指引

如果两个 CLI 都没有安装，请安装其中一个 runtime 并登录：

```bash
npm install -g @openai/codex
codex login
```

```bash
npm install -g @anthropic-ai/claude-code
claude
```

安装 CLI 需要 Node.js/npm。账号登录是交互式的、属于用户本人；请勿将密码或 token 粘贴到聊天中。

## 准备什么？

安装交给 Claude Code 或 Codex 即可。使用者主要需要准备：

- **Claude Code 或 Codex CLI**：已登录的订阅型 CLI runtime
- **KIS API key**：韩国价格、OHLCV、技术指标、财务/市场数据
- **Naver Developers key**：韩国本地新闻搜索
- **DART API key**：公告、公司标识符、事件上下文
- **ECOS API key**：韩国银行宏观数据

API key 只需要填写到 `.env` 一次。发放链接见下方 [API Key](#api-key)。

更多配置参考：

- [AI agent installation guide](llm.txt)
- [`.env.example`](.env.example)
- [Configuration guide](docs/configuration.md)
- [API key guide](docs/api-keys.md)
- [한국어 README](README.ko.md)
- [English README](README.md)

## API Key

| Key | 用途 | 是否必需 | 获取链接 |
|---|---|---:|---|
| `KIS_APP_KEY`, `KIS_APP_SECRET` | 韩国价格/OHLCV/指标/市场数据 | 推荐 | [KIS Developers](https://apiportal.koreainvestment.com/) |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 韩国本地新闻搜索 | 推荐 | [Naver Developers](https://developers.naver.com/apps/#/register) |
| `DART_API_KEY` | 公告、公司标识符、事件上下文 | 推荐 | [OpenDART](https://opendart.fss.or.kr/) |
| `ECOS_API_KEY` | 韩国宏观经济统计 | 推荐 | [ECOS Open API](https://ecos.bok.or.kr/api/) |
| `FRED_API_KEY` | 全球宏观补充指标 | 可选 | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `SEC_USER_AGENT` | 访问 SEC EDGAR 时的识别信息 | 可选 | [SEC guide](https://www.sec.gov/os/accessing-edgar-data) |
| `NOTION_API_TOKEN` | Notion report export | 可选 | [Notion integrations](https://developers.notion.com/guides/get-started/internal-connections) |
| `TELEGRAM_BOT_TOKEN` | 通知 / bot 集成 | 可选 | [BotFather](https://t.me/BotFather) |

详细发放方法和安全注意事项见 [docs/api-keys.md](docs/api-keys.md)。

## 使用示例

支持的韩国股票输入：

```text
005930
Samsung Electronics
삼성전자
000660
SK hynix
SK하이닉스
```

请求示例：

```text
Analyze Samsung Electronics Korean stock
三星电子韩国股票分析
005930 분석해줘
```

OpenClaw / Notion helper：

```bash
python .openclaw/skills/tradingagents-korea-analysis/scripts/run_analysis_to_notion.py \
  --ticker 005930 \
  --date YYYY-MM-DD \
  --timeout 7200
```

> 美股/海外股票，如 `AAPL`、`SPCX` 或 “Apple overseas stock”，建议使用独立的 US/overseas workflow。

## 架构

```text
用户请求
  ↓
股票代码 / 公司名解析
  ↓
数据预取
  ├─ KIS
  ├─ DART
  ├─ ECOS
  ├─ Naver News
  └─ yfinance
  ↓
Feature packet
  ├─ Market packet
  ├─ Fundamentals packet
  ├─ News packet
  └─ Macro / disclosure context
  ↓
TradingAgents workflow
  ├─ Market Analyst
  ├─ News Analyst
  ├─ Fundamentals Analyst
  ├─ Bull / Bear Researchers
  ├─ Trader
  ├─ Risk Manager
  └─ Portfolio Manager
  ↓
Markdown / Notion report
```

<p align="center">
  <img src="assets/schema.png" alt="TradingAgents framework schema" width="90%">
</p>

更多说明：

- [Architecture](docs/architecture.md)
- [Data sources](docs/data-sources.md)
- [Data source architecture](docs/data-source-architecture.md)

## 与原版 TradingAgents 的区别

| 维度 | 原版 TradingAgents | TradingAgents Korea |
|---|---|---|
| 市场重点 | 全球/美股导向的 ticker workflow | 韩国股票优先 |
| 主要市场数据 | 通用市场数据 provider | 以 KIS 为中心的韩国市场数据 |
| 公告上下文 | 通用公司/新闻上下文 | DART 公告和事件上下文 |
| 宏观上下文 | 全球宏观/新闻 | ECOS/BOK 韩国宏观层 |
| 新闻 | 全球/社交/新闻源 | Naver News + yfinance 补充视角 |
| 语言 | 主要是英文 workflow | 英文/韩文/中文文档 + 韩语报告输出 |
| LLM 执行 | API provider 导向 | Claude Code / Codex CLI 订阅型 runtime 优先 |
| 输出 | CLI/package 结果 | 长篇高级 Markdown + 可选 Notion export |

## 示例报告

已脱敏的公开示例报告：

- [三星电子 005930 报告 — 2026-06-30](examples/reports/zh/samsung-005930-2026-06-30.md)
- [SK 海力士 000660 报告 — 2026-06-30](examples/reports/zh/sk-hynix-000660-2026-06-30.md)
- [旧版三星电子 005930 demo 报告](examples/reports/samsung-005930-demo.md)

示例报告包含：

- 市场与技术面上下文
- 新闻与情绪上下文
- 基本面与公告上下文
- 宏观环境
- Bull case / bear case
- 交易计划
- 风险审查
- 组合经理最终判断

## 仓库结构

```text
TradingAgents-KR/
├── tradingagents/          # Core agents, graph, dataflows
├── cli/                    # Interactive CLI
├── docs/                   # Public docs and design notes
├── examples/reports/       # Localized sanitized sample reports
├── .openclaw/skills/       # OpenClaw helper skill
├── main.py                 # Root entry point
├── llm.txt                 # Detailed setup guide for AI agents
├── .env.example            # Safe env template
├── README.md               # English README
├── README.ko.md            # Korean README
└── README.zh.md            # Simplified Chinese README
```

## 公开发布安全检查

公开仓库前请先检查：

- [Security public release checklist](SECURITY_PUBLIC_RELEASE_CHECKLIST.md)
- [Public release guide](docs/public-release-guide.md)

不要提交：

- `.env`
- API key 或 token
- KIS 账户标识符
- Notion token 或私有 page URL
- Telegram bot token
- 私有报告 export 文件
- 个人本地路径

## 路线图

- [ ] KRX sector rotation packet
- [ ] DART XBRL TTM fundamentals
- [ ] ECOS macro regime model
- [ ] KIS realtime market snapshot
- [ ] Backtesting / evaluation harness
- [ ] MCP server mode
- [ ] Web dashboard
- [ ] English report mode

## 致谢

本项目基于原版 TradingAgents 框架：

- Upstream: <https://github.com/TauricResearch/TradingAgents>
- Upstream paper: <https://arxiv.org/abs/2412.20138>

韩国市场数据集成和 workflow 改动由本 fork 维护。

详见 [CREDITS.md](CREDITS.md) 和 [NOTICE.md](NOTICE.md)。

## 许可证

Apache License 2.0。详见 [LICENSE](LICENSE)。

---

<div align="center">

如果这个项目对你的韩国股票研究有帮助，欢迎给一个 star。

[Back to top](#readme-top)

</div>
