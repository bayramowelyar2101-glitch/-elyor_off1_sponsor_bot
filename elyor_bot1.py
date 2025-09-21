#!/usr/bin/env python3
# elyor_bot1.py
# Prepared for deployment. Bot UI/messages are in Turkmençe; admin-side comments are in Turkish here.
# IMPORTANT: Do NOT put your BOT_TOKEN in the code. Use environment variables.
# Usage locally: create a .env with BOT_TOKEN and ADMIN_IDS, then run: python elyor_bot1.py

import os
import sqlite3
import time
import logging
import threading
import asyncio
from typing import List
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

# Optional web server for uptime pings
from aiohttp import web

# Config from environment
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS_ENV = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = [int(x) for x in ADMIN_IDS_ENV.split(",") if x.strip().isdigit()]
DB_PATH = os.environ.get("DATABASE_PATH", "elyor.db")
PORT = int(os.environ.get("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required.")

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# DB helpers
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE NOT NULL,
            title TEXT,
            max_subs INTEGER,
            order_num INTEGER DEFAULT 1000,
            show_until INTEGER,
            bot_admin INTEGER DEFAULT 0,
            subs_count INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vpn_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            added_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    conn.commit()
    conn.close()

def db_execute(query, params=(), fetch=False):
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

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def parse_channel_identifier(s: str) -> str:
    s = s.strip()
    if s.startswith("http://") or s.startswith("https://"):
        if "t.me/" in s:
            s = s.split("t.me/")[-1]
    if s.startswith("t.me/"):
        s = s.split("t.me/")[-1]
    if not s.startswith("@"):
        s = "@" + s
    return s

def active_channels():
    now = int(time.time())
    rows = db_execute("SELECT id,link,title,max_subs,order_num,show_until,bot_admin,subs_count FROM channels ORDER BY order_num ASC", fetch=True)
    out = []
    for r in rows:
        cid, link, title, max_subs, order_num, show_until, bot_admin, subs_count = r
        if show_until and show_until > 0 and now > show_until:
            continue
        out.append({"id": cid, "link": link, "title": title or link, "max_subs": max_subs, "order_num": order_num, "bot_admin": bot_admin, "subs_count": subs_count})
    return out

async def check_user_member(app: Application, channel_identifier: str, user_id: int) -> bool:
    try:
        member = await app.bot.get_chat_member(chat_id=channel_identifier, user_id=user_id)
        status = member.status
        return status not in ("left", "kicked")
    except Exception as e:
        logger.warning("check_user_member error: %s", e)
        return False

async def check_bot_admin(app: Application, channel_identifier: str) -> bool:
    try:
        me = await app.bot.get_me()
        member = await app.bot.get_chat_member(chat_id=channel_identifier, user_id=me.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.warning("check_bot_admin error: %s", e)
        return False

def format_channel_buttons(channels):
    buttons = []
    row = []
    for ch in channels:
        # use callback_data chan:<id>
        row.append(InlineKeyboardButton(f"🔔 {ch['title']}", callback_data=f"chan:{ch['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ Agza boldum", callback_data="confirm_subs")])
    return InlineKeyboardMarkup(buttons)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        db_execute("INSERT OR REPLACE INTO users(user_id, username, first_name) VALUES (?, ?, ?)", (user.id, user.username or "", user.first_name or ""))
    bot_name = (await context.bot.get_me()).username
    chs = active_channels()
    if not chs:
        await update.message.reply_text("👋 Salam! Häzirki wagtda admin hiç hili kanal bellänok.")
        return
    text = (
        f"👋 Salam *{user.first_name or user.username or user.id}*!\n"
        f"🤖 @{bot_name} botyna hoş geldiňiz.\n\n"
        "🔑 VPN kody almak üçin aşakdaky kanallara agza boluň:\n"
        "1️⃣ Kanallara girip *Agza boluň*.\n"
        "2️⃣ Soňra *Agza boldum ✅* düwmesine basyň.\n\n"
        "📌 Eger ähli kanallara agza bolsaňyz, düwme basanyňyzda VPN kody (hediye) size eltiler."
    )
    kb = format_channel_buttons(chs)
    await update.message.reply_text(text, reply_markup=kb, parse_mode=constants.ParseMode.MARKDOWN)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    if data == "confirm_subs":
        chs = active_channels()
        missing = []
        for ch in chs:
            ok = await check_user_member(context.application, ch["link"], user.id)
            if not ok:
                missing.append(ch)
        if missing:
            lines = ["⚠️ Siz ähli kanallara agza bolmadyňyz!", "📌 Agza bolmadyk kanallaryňyz:"]
            for m in missing:
                lines.append(f"➡️ {m['title']} ({m['link']})")
            lines.append("\n🔁 Ýene bir gezek barlap görüň.")
            await query.edit_message_text("\n".join(lines))
            return
        row = db_execute("SELECT id, text FROM vpn_codes ORDER BY created_at DESC LIMIT 1", fetch=True)
        if not row:
            await query.edit_message_text("🎉 Siz ähli kanallara agza boldyňyz.\n\n🔑 Häzirki wagtda admin hiç hili VPN kody bellänok.")
            return
        vpn_id, vpn_text = row[0]
        try:
            await context.bot.send_message(chat_id=user.id, text=f"🎉 Gutlaýarys! ✅\n\n🔑 *VPN kodyňyz*:\n{vpn_text}", parse_mode=constants.ParseMode.MARKDOWN)
            db_execute("UPDATE vpn_codes SET sent_count = sent_count + 1 WHERE id = ?", (vpn_id,))
            await query.edit_message_text("✅ Size VPN kody ugradyldy. Habar ulanylan ýagdaýy admin panelinden görünýär.")
        except Exception as e:
            logger.exception("Failed to send vpn code: %s", e)
            await query.edit_message_text("⚠️ Ýalňyşlyk boldy. Admin bilen habarlaşyň.")
        return
    if data.startswith("chan:"):
        cid = int(data.split(":",1)[1])
        row = db_execute("SELECT link,title FROM channels WHERE id = ?", (cid,), fetch=True)
        if not row:
            await query.edit_message_text("Kanal tapylmady.")
            return
        link, title = row[0]
        send_text = f"📢 *{title}*\nLink: {link}\n\n➡️ Kanala girip *Agza boluň* we soňra geri gelip *Agza boldum ✅* düwmesine basyň."
        if link.startswith("@"):
            send_text += f"\n\n🔗 https://t.me/{link.lstrip('@')}"
        await query.edit_message_text(send_text, parse_mode=constants.ParseMode.MARKDOWN)
        return

# Admin commands (simple text-based)
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    text = (
        "🛠️ *Admin komandalary*:\n\n"
        "/addchannel link|title|max_or_maxword|order_num|hours\n"
        "/removechannel <id>\n"
        "/listchannels\n\n"
        "/addvpn <tekst>\n"
        "/listvpn\n\n"
        "/broadcast_users <mesaj>\n"
        "/broadcast_channels <mesaj>\n"
        "/stats\n"
    )
    await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)

async def addchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    if not context.args:
        await update.message.reply_text("Ulanylmasy: /addchannel link|title|max_or_maxword|order_num|hours")
        return
    payload = " ".join(context.args)
    parts = payload.split("|")
    if len(parts) < 5:
        await update.message.reply_text("Ulanylmasy: /addchannel link|title|max_or_maxword|order_num|hours")
        return
    link_raw, title, max_part, order_part, hours_part = [p.strip() for p in parts[:5]]
    link = parse_channel_identifier(link_raw)
    try:
        order_num = int(order_part)
    except:
        order_num = 1000
    if max_part.lower() in ("max", "limitsiz", "unlimited", "none", "-1"):
        max_subs = -1
    else:
        try:
            max_subs = int(max_part)
        except:
            max_subs = -1
    try:
        hours = float(hours_part)
        show_until = int(time.time() + int(hours * 3600))
    except:
        show_until = None
    db_execute("INSERT OR IGNORE INTO channels(link,title,max_subs,order_num,show_until) VALUES (?, ?, ?, ?, ?)", (link, title, max_subs, order_num, show_until))
    ba = 1 if await check_bot_admin(context.application, link) else 0
    db_execute("UPDATE channels SET bot_admin = ? WHERE link = ?", (ba, link))
    await update.message.reply_text(f"Kanal goşuldy: {title} ({link})\\nBot admin status: {'Bar' if ba else 'Ýok'}")

async def removechannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    if not context.args:
        await update.message.reply_text("Ulanylmasy: /removechannel <id>")
        return
    try:
        cid = int(context.args[0])
    except:
        await update.message.reply_text("Id san bolmaly.")
        return
    db_execute("DELETE FROM channels WHERE id = ?", (cid,))
    await update.message.reply_text(f"Kanal id={cid} pozuldy.")

async def listchannels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    rows = db_execute("SELECT id,link,title,max_subs,order_num,show_until,bot_admin,subs_count FROM channels ORDER BY order_num ASC", fetch=True)
    if not rows:
        await update.message.reply_text("Kanal tapylmady.")
        return
    lines = ["📋 *Kanal sanawy:*"]
    for r in rows:
        cid, link, title, max_subs, order_num, show_until, bot_admin, subs_count = r
        max_text = "max" if (max_subs is None or max_subs == -1) else str(max_subs)
        until_text = datetime.utcfromtimestamp(show_until).isoformat() if show_until else "heç"
        lines.append(f"ID:{cid} | {title} | {link} | max:{max_text} | order:{order_num} | gösterim_son: {until_text} | bot_admin:{bot_admin} | subs:{subs_count}")
    await update.message.reply_text("\\n".join(lines), parse_mode=constants.ParseMode.MARKDOWN)

async def addvpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    if not context.args:
        await update.message.reply_text("Ulanylmasy: /addvpn <tekst>")
        return
    text = " ".join(context.args)
    db_execute("INSERT INTO vpn_codes(text) VALUES (?)", (text,))
    await update.message.reply_text("VPN kody (tekst) goşuldy.")

async def listvpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    rows = db_execute("SELECT id, text, sent_count, created_at FROM vpn_codes ORDER BY created_at DESC", fetch=True)
    if not rows:
        await update.message.reply_text("VPN kod tapylmady.")
        return
    lines = ["📦 *VPN kodlar:*"]
    for r in rows:
        vid, text, sent, created = r
        ts = datetime.utcfromtimestamp(created).isoformat()
        lines.append(f"ID:{vid} | sent:{sent} | created:{ts}\\n{text}\\n----")
    await update.message.reply_text("\\n".join(lines), parse_mode=constants.ParseMode.MARKDOWN)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    rows = db_execute("SELECT COUNT(*) FROM users", fetch=True)
    users_count = rows[0][0] if rows else 0
    chs = db_execute("SELECT COUNT(*) FROM channels", fetch=True)[0][0]
    vpcs = db_execute("SELECT COUNT(*) FROM vpn_codes", fetch=True)[0][0]
    await update.message.reply_text(f"📊 Statistika:\\nUlanyjy sany: {users_count}\\nKanal sany: {chs}\\nVPN kod sany: {vpcs}")

async def broadcast_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Ulanylmasy: /broadcast_users <mesaj>")
        return
    rows = db_execute("SELECT user_id FROM users", fetch=True)
    if not rows:
        await update.message.reply_text("Ulanyjy tapylmady.")
        return
    count = 0
    for r in rows:
        uid = r[0]
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            count += 1
        except Exception as e:
            logger.warning("broadcast to %s failed: %s", uid, e)
    await update.message.reply_text(f"Ugratdyldy: {count} ulanyjyga.")

async def broadcast_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("Siz admin emezsiniz.")
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Ulanylmasy: /broadcast_channels <mesaj>")
        return
    rows = db_execute("SELECT link FROM channels WHERE bot_admin = 1", fetch=True)
    if not rows:
        await update.message.reply_text("Bot admin bolmadyk kanal tapylmady.")
        return
    count = 0
    for r in rows:
        link = r[0]
        try:
            await context.bot.send_message(chat_id=link, text=text)
            count += 1
        except Exception as e:
            logger.warning("broadcast channel %s failed: %s", link, e)
    await update.message.reply_text(f"Ugratdyldy: {count} kanal/gruppe.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# -- Simple aiohttp ping server so uptime monitors can ping the app --
async def start_ping_server(port: int):
    app = web.Application()
    async def handle(request):
        return web.Response(text="OK")
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Ping server started on port %s", port)

def run_ping_server_in_thread(port: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_ping_server(port))
    loop.run_forever()

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    # admin commands
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CommandHandler("addchannel", addchannel))
    application.add_handler(CommandHandler("removechannel", removechannel))
    application.add_handler(CommandHandler("listchannels", listchannels))
    application.add_handler(CommandHandler("addvpn", addvpn))
    application.add_handler(CommandHandler("listvpn", listvpn))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("broadcast_users", broadcast_users))
    application.add_handler(CommandHandler("broadcast_channels", broadcast_channels))
    application.add_error_handler(error_handler)

    # Start ping server in background thread (keeps app alive with uptime monitors)
    try:
        t = threading.Thread(target=run_ping_server_in_thread, args=(PORT,), daemon=True)
        t.start()
    except Exception as e:
        logger.warning("Could not start ping server thread: %s", e)

    logger.info("Starting bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
