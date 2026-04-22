#!/usr/bin/env python3
"""
bot/main.py — 化粧品宣稱檢核助手 Telegram Bot
指令：
  /start   — 歡迎訊息 + 免責聲明
  /check <文字>  — 核心查詢
  直接傳文字    — 同 /check
白名單：只接受 .env 的 ALLOWED_USER_IDS（Kenji 個人使用）
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# 載入 .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 設定 logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# 載入 checker（lazy，避免啟動時強依賴）
from bot.checker import DISCLAIMER, get_checker

WELCOME_TEXT = (
    "👋 *化粧品宣稱檢核助手*\n"
    "\n"
    "直接傳入你想查詢的宣稱文字，或使用 `/check <宣稱文字>`。\n"
    "\n"
    "範例：\n"
    "• `淡化黑眼圈`\n"
    "• `這條乳液可以抗菌消炎`\n"
    "• `促進膠原蛋白合成，緊緻肌膚`\n"
    "\n"
    "*支援查詢：*\n"
    "🔍 單一詞句 — 判斷合法性與佐證需求\n"
    "🔍 完整文案 — 掃描所有宣稱並彙整判定\n"
    "\n"
    "---\n"
    + DISCLAIMER
)

MAX_QUERY_LENGTH = 500


# ── 白名單 ────────────────────────────────────────────────────
def _get_allowed_ids() -> set[int]:
    raw = os.environ.get("ALLOWED_USER_IDS", "").strip()
    if not raw:
        return set()
    result: set[int] = set()
    for x in raw.split(","):
        x = x.strip()
        if x.isdigit():
            result.add(int(x))
    return result


def is_allowed(user_id: int) -> bool:
    return user_id in _get_allowed_ids()


# ── 輔助：傳送長訊息（Telegram 單則最大 4096 字元）────────────
async def send_long(update: Update, text: str) -> None:
    MAX = 4000
    for start in range(0, len(text), MAX):
        await update.message.reply_text(
            text[start : start + MAX],
            parse_mode=None,  # 純文字，避免 Markdown 跳脫問題
        )


# ── 核心查詢邏輯 ──────────────────────────────────────────────
async def _run_check(update: Update, query: str) -> None:
    if len(query) > MAX_QUERY_LENGTH:
        await update.message.reply_text(
            f"⚠️ 宣稱文字過長（{len(query)} 字元，上限 {MAX_QUERY_LENGTH}）。\n"
            "請縮短後再試，或分段查詢。"
        )
        return

    await update.message.reply_text("⏳ 檢核中，請稍候…")

    checker = get_checker()
    result = checker.check(query)
    await send_long(update, result.reply_text)


# ── Handlers ─────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⚙️ 服務測試中，尚未開放。")
        logger.info("拒絕非白名單使用者：%s (%d)", user.username, user.id)
        return
    await send_long(update, WELCOME_TEXT)


async def check_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⚙️ 服務測試中，尚未開放。")
        return

    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text(
            "請在指令後加入宣稱文字，例如：\n`/check 淡化黑眼圈`"
        )
        return

    await _run_check(update, query)


async def handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⚙️ 服務測試中，尚未開放。")
        return

    query = (update.message.text or "").strip()
    if not query:
        return

    await _run_check(update, query)


# ── 錯誤處理 ──────────────────────────────────────────────────
async def error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    logger.error("Telegram 錯誤：%s", context.error, exc_info=True)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "⚠️ 發生錯誤，請稍後再試。若問題持續，請聯繫管理員。"
        )


# ── 主程式 ────────────────────────────────────────────────────
def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or token == "put_your_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN 未設定，請在 .env 填入正確 Token")
        sys.exit(1)

    allowed = _get_allowed_ids()
    if not allowed:
        logger.warning("ALLOWED_USER_IDS 未設定，所有使用者均被拒絕")

    logger.info("啟動化粧品宣稱檢核助手，白名單使用者：%s", allowed)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
