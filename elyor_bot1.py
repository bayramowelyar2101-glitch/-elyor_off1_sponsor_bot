#!/usr/bin/env python3
# elyor_bot1.py
# Full-featured sponsor bot with inline admin panel and SQLite persistence.
# Designed for python-telegram-bot v20.x (Application builder).
# Updated:
#   - Start text değiştirildi
#   - Kanal butonları direk URL (mümkünse)
#   - Kullanıcıya sadece bot_admin=1 olan kanallar gösteriliyor

import os
import logging
import sqlite3
import time
import asyncio
import html
from datetime import datetime
from typing import List, Dict, Any

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------- Configuration ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
DB_PATH = os.getenv("DB_PATH", "elyor_bot.db")

# ---------------- Logging ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("elyor_bot1")

# ---------------- Database ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        added_at INTEGER DEFAULT (strftime('%s','now'))
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT UNIQUE NOT NULL,
        title TEXT,
        max_subs INTEGER DEFAULT -1,
        order_num INTEGER DEFAULT 1000,
        show_until INTEGER DEFAULT 0,
        bot_admin INTEGER DEFAULT 0,
        subs_count INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS vpn_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        sent_count INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS vpn_sent_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vpn_id INTEGER,
        user_id INTEGER,
        sent_at INTEGER DEFAULT (strftime('%s','now'))
    )""")
    conn.commit()
    conn.close()

def db_execute(query: str, params: tuple = (), fetch: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query, params)
    if fetch:
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return rows
    conn.commit()
    conn.close()
    return None

# ---------------- Utilities ----------------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def parse_channel_identifier(s: str) -> str:
    s = s.strip()
    if s.startswith("http://") or s.startswith("https://"):
        if "t.me/" in s:
            s = s.split("t.me/")[-1]
    if s.startswith("t.me/"):
        s = s.split("t.me/")[-1]
    if s == "":
        return s
    if s.startswith("-"):
        return s
    if not s.startswith("@"):
        s = "@" + s
    return s

def get_channels(active_only: bool = True, only_admin: bool = True) -> List[Dict[str, Any]]:
    now = int(time.time())
    rows = db_execute("SELECT id,link,title,max_subs,order_num,show_until,bot_admin,subs_count FROM channels ORDER BY order_num ASC", fetch=True) or []
    out = []
    for r in rows:
        cid, link, title, max_subs, order_num, show_until, bot_admin, subs_count = r
        if active_only and show_until and show_until > 0 and now > show_until:
            continue
        if only_admin and not bot_admin:
            continue
        out.append({
            "id": cid,
            "link": link,
            "title": title or link,
            "max_subs": max_subs,
            "order_num": order_num,
            "show_until": show_until,
            "bot_admin": bool(bot_admin),
            "subs_count": subs_count
        })
    return out

async def bot_is_admin_of(app: Application, channel: str) -> bool:
    try:
        me = await app.bot.get_me()
        member = await app.bot.get_chat_member(chat_id=channel, user_id=me.id)
        return getattr(member, "status", "") in ("administrator", "creator")
    except Exception as e:
        logger.debug("bot_is_admin_of failed for %s: %s", channel, e)
        return False

async def check_user_member(app: Application, channel: str, user_id: int) -> bool:
    try:
        member = await app.bot.get_chat_member(chat_id=channel, user_id=user_id)
        status = getattr(member, "status", None)
        return status not in ("left", "kicked", None)
    except Exception as e:
        logger.debug("check_user_member error for %s user %s: %s", channel, user_id, e)
        return False

def make_channels_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = []
    currow = []
    for ch in channels:
        link = ch.get("link", "") or ""
        url = None
        if link.startswith("@"):
            url = f"https://t.me/{link.lstrip('@')}"
        elif link.startswith("http://") or link.startswith("https://"):
            url = link
        if url:
            currow.append(InlineKeyboardButton(f"🔔 {ch['title']}", url=url))
        else:
            currow.append(InlineKeyboardButton(f"🔔 {ch['title']}", callback_data=f"chan:{ch['id']}"))
        if len(currow) == 2:
            rows.append(currow)
            currow = []
    if currow:
        rows.append(currow)
    rows.append([InlineKeyboardButton("✅ Agza boldum", callback_data="confirm_subs")])
    return InlineKeyboardMarkup(rows)

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        db_execute("INSERT OR REPLACE INTO users(user_id, username, first_name) VALUES (?, ?, ?)",
                   (user.id, user.username or "", user.first_name or ""))
    bot_me = await context.bot.get_me()
    bot_name = bot_me.username or ""
    channels = get_channels(active_only=True, only_admin=True)
    if not channels:
        await update.message.reply_text("👋 Salam! Häzirki wagtda admin hiç hili kanal bellänok.")
        return
    safe_name = html.escape(user.first_name or user.username or str(user.id))
    safe_bot = html.escape(bot_name)
    text = (
        f"👋 Salam <b>{safe_name}</b>!\n"
        f"🤖 @{safe_bot} botuna hoş geldiňiz.\n\n"
        "🔑 VPN kody almak üçin aşakdaky kanallara agza boluň:\n"
        "1️⃣ Her kanala girip agza boluň.\n"
        "2️⃣ Soňra <b>Agza boldum</b> düwmesine basyň.\n\n"
        "📌 Bu bot size admin tarapyndan düzülen full tizlikde 7/24 işleýän VPN kodyny mugt berýär."
    )
    kb = make_channels_keyboard(channels)
    await update.message.reply_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

# ---------------- Startup / Main ----------------
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    logger.info("Bot starting...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
