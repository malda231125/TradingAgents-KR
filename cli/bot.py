"""Telegram bot for TradingAgents Korea.

Send a Korean stock ticker (e.g. "005930") to the bot and receive
a full multi-agent analysis report.

Usage:
    python -m cli.bot

Requires:
    TELEGRAM_BOT_TOKEN - Bot token from BotFather
    TELEGRAM_USER_ID   - Allowed user ID (single-user security)
"""

import asyncio
import logging
import os
import traceback
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.prefetch import clear_cache

logger = logging.getLogger(__name__)


def _parse_allowed_user_id(value: str | None) -> int:
    """Parse TELEGRAM_USER_ID safely.

    Empty strings should behave the same as an unset variable so that a
    placeholder `.env` entry does not break module import or test discovery.
    """
    raw = (value or "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid TELEGRAM_USER_ID value %r; falling back to 0", value)
        return 0


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = _parse_allowed_user_id(os.environ.get("TELEGRAM_USER_ID"))


def _is_authorized(update: Update) -> bool:
    """Check if the message sender is the authorized user."""
    return update.effective_user.id == ALLOWED_USER_ID


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not _is_authorized(update):
        return

    await update.message.reply_text(
        "TradingAgents Korea 봇입니다.\n\n"
        "사용법:\n"
        "- 종목코드 전송 (예: 005930)\n"
        "- /analyze 005930\n"
        "- /clear_cache — 데이터 캐시 초기화\n"
        "- /help — 도움말"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if not _is_authorized(update):
        return

    await update.message.reply_text(
        "TradingAgents Korea\n\n"
        "명령어:\n"
        "- 종목코드 (예: 005930) — 전체 분석 실행\n"
        "- /analyze <종목코드> — 전체 분석 실행\n"
        "- /clear_cache — 데이터 캐시 초기화\n"
        "- /help — 이 도움말\n\n"
        "분석 에이전트: Market, News, Fundamentals\n"
        "토론 에이전트: Bull/Bear Researcher\n"
        "리스크 에이전트: Aggressive/Conservative/Neutral\n"
        "최종 결정: Portfolio Manager"
    )


async def clear_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear_cache command."""
    if not _is_authorized(update):
        return

    count = clear_cache()
    await update.message.reply_text(f"캐시 초기화 완료: {count}개 파일 삭제")


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /analyze <ticker> command."""
    if not _is_authorized(update):
        return

    if not context.args:
        await update.message.reply_text("종목코드를 입력해주세요. 예: /analyze 005930")
        return

    ticker = context.args[0].strip()
    await _run_analysis(update, ticker)


async def batch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /batch <ticker1> <ticker2> ... command."""
    if not _is_authorized(update):
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "종목코드 2개 이상 입력해주세요.\n예: /batch 005930 000660 035420"
        )
        return

    tickers = [t.strip() for t in context.args]
    trade_date = datetime.now().strftime("%Y-%m-%d")

    status_msg = await update.message.reply_text(
        f"배치 분석 시작: {', '.join(tickers)} ({trade_date})\n"
        f"총 {len(tickers)}개 종목 순차 분석 중..."
    )

    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, _run_batch, tickers, trade_date
        )

        # Format summary
        lines = [f"[배치 분석 완료] {trade_date}\n"]
        for ticker, result in results.items():
            if result["error"]:
                lines.append(f"{ticker}: 실패 - {result['error']}")
            else:
                signal = result["signal"] or "N/A"
                lines.append(f"{ticker}: {signal}")

        summary = "\n".join(lines)

        if len(summary) > 4000:
            summary = summary[:4000] + "\n\n... (일부 생략)"

        await update.message.reply_text(summary)

        # Send individual decisions
        for ticker, result in results.items():
            if result["error"] or not result["decision"]:
                continue
            decision = result["decision"]
            if len(decision) > 4000:
                decision = decision[:4000] + "\n\n... (일부 생략)"
            await update.message.reply_text(f"[{ticker}] 상세 결과\n\n{decision}")

    except Exception as e:
        logger.error("Batch analysis failed: %s", traceback.format_exc())
        try:
            await status_msg.edit_text(f"배치 분석 실패: {str(e)}")
        except Exception:
            await update.message.reply_text(f"배치 분석 실패: {str(e)}")


def _run_batch(tickers: list, trade_date: str) -> dict:
    """Run batch analysis synchronously (called from thread pool)."""
    config = DEFAULT_CONFIG.copy()
    graph = TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        config=config,
    )
    return graph.batch_propagate(tickers, trade_date)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages — treat as ticker if it looks like one."""
    if not _is_authorized(update):
        return

    text = update.message.text.strip()

    # Accept Korean stock codes (6 digits) or company names
    if text.isdigit() and len(text) == 6:
        await _run_analysis(update, text)
    elif len(text) <= 20 and not text.startswith("/"):
        # Might be a company name or short ticker
        await _run_analysis(update, text)
    else:
        await update.message.reply_text(
            "종목코드 6자리 또는 종목명을 입력해주세요.\n예: 005930"
        )


async def _run_analysis(update: Update, ticker: str):
    """Execute the full TradingAgents analysis pipeline for a ticker."""
    trade_date = datetime.now().strftime("%Y-%m-%d")

    status_msg = await update.message.reply_text(
        f"분석 시작: {ticker} ({trade_date})\n"
        f"애널리스트 3명 병렬 분석 중..."
    )

    try:
        # Run the blocking analysis in a thread pool
        loop = asyncio.get_event_loop()
        final_state, signal = await loop.run_in_executor(
            None, _run_graph, ticker, trade_date
        )

        # Send progress: debate phase
        await status_msg.edit_text(
            f"분석 진행: {ticker}\n"
            f"애널리스트 완료 → 리서치 토론 + 트레이딩 + 리스크 분석 완료"
        )

        # Extract final decision
        decision = final_state.get("final_trade_decision", "결정 없음")

        # Truncate if too long for Telegram (4096 char limit)
        if len(decision) > 4000:
            decision = decision[:4000] + "\n\n... (일부 생략)"

        # Send final result as new message (triggers notification)
        await update.message.reply_text(
            f"[{ticker}] 분석 완료\n"
            f"날짜: {trade_date}\n"
            f"신호: {signal}\n\n"
            f"{decision}"
        )

    except Exception as e:
        error_msg = f"분석 실패: {ticker}\n에러: {str(e)}"
        logger.error("Analysis failed for %s: %s", ticker, traceback.format_exc())

        try:
            await status_msg.edit_text(error_msg)
        except Exception:
            await update.message.reply_text(error_msg)


def _run_graph(ticker: str, trade_date: str):
    """Run TradingAgentsGraph synchronously (called from thread pool)."""
    config = DEFAULT_CONFIG.copy()
    graph = TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        config=config,
    )
    return graph.propagate(ticker, trade_date)


def main():
    """Start the Telegram bot."""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return
    if not ALLOWED_USER_ID:
        print("Error: TELEGRAM_USER_ID not set")
        return

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear_cache", clear_cache_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("batch", batch_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print(f"TradingAgents Korea Bot started (user: {ALLOWED_USER_ID})")
    app.run_polling()


if __name__ == "__main__":
    main()
