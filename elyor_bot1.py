#!/usr/bin/env python3
# elyor_bot1.py
# Advanced sponsor bot with inline admin panel, sqlite persistence, HTML-escaped output.
# Designed for python-telegram-bot v20.x (Application builder).

import os
import logging
import sqlite3
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

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
from telegram.helpers import escape_html

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

# ---------------- Database helpers ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            added_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    # Channels
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE NOT NULL,
            title TEXT,
            max_subs INTEGER DEFAULT -1,
            order_num INTEGER DEFAULT 1000,
            show_until INTEGER DEFAULT 0,
            bot_admin INTEGER DEFAULT 0,
            subs_count INTEGER DEFAULT 0
        )
    """)
    # VPN codes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vpn_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    # Log of vpn sent
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vpn_sent_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vpn_id INTEGER,
            user_id INTEGER,
            sent_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
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
    # Accept t.me links, usernames, or -100... IDs
    s = s.strip()
    if s.startswith("http://") or s.startswith("https://"):
        if "t.me/" in s:
            s = s.split("t.me/")[-1]
    if s.startswith("t.me/"):
        s = s.split("t.me/")[-1]
    # If it's numeric channel id starting with -100 or digits keep as is
    if s.startswith("-"):
        return s
    if not s.startswith("@"):
        s = "@" + s
    return s

def get_channels(active_only: bool = True) -> List[Dict[str, Any]]:
    now = int(time.time())
    rows = db_execute("""
        SELECT id, link, title, max_subs, order_num, show_until, bot_admin, subs_count
        FROM channels
        ORDER BY order_num ASC
    """, fetch=True)
    out = []
    for r in rows:
        cid, link, title, max_subs, order_num, show_until, bot_admin, subs_count = r
        if active_only and show_until and show_until > 0 and now > show_until:
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
        logger.warning("bot_is_admin_of failed for %s: %s", channel, e)
        return False

async def check_user_member(app: Application, channel: str, user_id: int) -> bool:
    try:
        member = await app.bot.get_chat_member(chat_id=channel, user_id=user_id)
        status = getattr(member, "status", None)
        return status not in ("left", "kicked", None)
    except Exception as e:
        logger.warning("check_user_member error for %s user %s: %s", channel, user_id, e)
        return False

def make_channels_keyboard(channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = []
    currow = []
    for ch in channels:
        # Show title and link via callback which opens details (or open link directly)
        currow.append(InlineKeyboardButton(f"🔔 {ch['title']}", callback_data=f"chan:{ch['id']}"))
        if len(currow) == 2:
            rows.append(currow)
            currow = []
    if currow:
        rows.append(currow)
    rows.append([InlineKeyboardButton("✅ Agza boldum", callback_data="confirm_subs")])
    return InlineKeyboardMarkup(rows)

# ---------------- User Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        db_execute("INSERT OR REPLACE INTO users(user_id, username, first_name) VALUES (?, ?, ?)",
                   (user.id, user.username or "", user.first_name or ""))
    bot_name = (await context.bot.get_me()).username
    channels = get_channels(active_only=True)
    if not channels:
        await update.message.reply_text("👋 Salam! Häzirki wagtda admin hiç hili kanal bellänok.")
        return

    # Escape dynamic values
    safe_name = escape_html(user.first_name or user.username or str(user.id))
    text = (
        f"👋 Salam <b>{safe_name}</b>!\n"
        f"🤖 @{escape_html(bot_name)} botyna hoş geldiňiz.\n\n"
        "🔑 VPN kody almak üçin aşakdaky kanallara agza boluň:\n"
        "1️⃣ Her kanala girip agza boluň.\n"
        "2️⃣ Soňra <b>Agza boldum</b> düwmesine basyň.\n\n"
        "📌 Eger ähli kanallara agza bolsaňyz, size admin tarapyndan bellän VPN (hediye) ugradylar."
    )
    kb = make_channels_keyboard(channels)
    await update.message.reply_text(text, reply_markup=kb, parse_mode=constants.ParseMode.HTML)

async def callback_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    user = query.from_user

    # Confirm subscription
    if data == "confirm_subs":
        channels = get_channels(active_only=True)
        missing = []
        for ch in channels:
            ok = await check_user_member(context.application, ch["link"], user.id)
            if not ok:
                missing.append(ch)
            await asyncio.sleep(0.08)  # little delay
        if missing:
            lines = ["⚠️ Siz hemmesine agza bolmadyňyz!", "📌 Agza bolmadyk kanallaryňyz:"]
            for m in missing:
                lines.append(f"➡️ {escape_html(m['title'])} ({escape_html(m['link'])})")
            lines.append("\n🔁 Täzeden barlap görüň.")
            await query.edit_message_text("\n".join(lines), parse_mode=constants.ParseMode.HTML)
            return
        # all subscribed: send latest vpn code(s) added by admin
        rows = db_execute("SELECT id, text FROM vpn_codes ORDER BY created_at DESC LIMIT 1", fetch=True)
        if not rows:
            await query.edit_message_text("🎉 Siz ähli kanallara agza bolduňyz.\n\n🔑 Häzirki wagtda admin VPN kody goşmandyr.")
            return
        vpn_id, vpn_text = rows[0]
        try:
            # send privately and record
            await context.bot.send_message(chat_id=user.id, text=f"🎉 Gutlaýarys! ✅\n\n🔑 VPN kodyňyz:\n{escape_html(vpn_text)}", parse_mode=constants.ParseMode.HTML)
            db_execute("UPDATE vpn_codes SET sent_count = sent_count + 1 WHERE id = ?", (vpn_id,))
            db_execute("INSERT INTO vpn_sent_log(vpn_id, user_id) VALUES (?, ?)", (vpn_id, user.id))
            await query.edit_message_text("✅ Size VPN kody ugradyldy. Admin panelinden statistika bar.") 
        except Exception as e:
            logger.exception("Failed to send vpn code: %s", e)
            await query.edit_message_text("⚠️ VPN kody ugratmakda näsazlyk boldy. Admin bilen habarlaşyň.")
        return

    # Channel details
    if data.startswith("chan:"):
        try:
            cid = int(data.split(":", 1)[1])
        except:
            await query.edit_message_text("Nädogry kanal id.")
            return
        row = db_execute("SELECT link, title FROM channels WHERE id = ?", (cid,), fetch=True)
        if not row:
            await query.edit_message_text("Kanal tapylmady.")
            return
        link, title = row[0]
        send_text = (
            f"📢 <b>{escape_html(title or link)}</b>\n"
            f"Link: {escape_html(link)}\n\n"
            "➡️ Kanala girip agza boluň we soňra geri gelip <b>Agza boldum ✅</b> düwmesine basyň."
        )
        if link.startswith("@"):
            send_text += f"\n\n🔗 https://t.me/{escape_html(link.lstrip('@'))}"
        await query.edit_message_text(send_text, parse_mode=constants.ParseMode.HTML)
        return

    # Admin panel entry
    if data in ("admin_panel", "adm_open"):
        if not is_admin(user.id):
            await query.edit_message_text("Siz admin emezsiniz.")
            return
        await show_admin_panel(query, context)
        return

    # Admin callbacks
    if data.startswith("adm_"):
        if not is_admin(user.id):
            await query.edit_message_text("Siz admin emezsiniz.")
            return
        await admin_callbacks_dispatch(query, context)
        return

# ---------------- Admin UI & Logic ----------------
async def show_admin_panel(trigger, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanallar", callback_data="adm_channels")],
        [InlineKeyboardButton("🔑 VPN Kodlary", callback_data="adm_vpns")],
        [InlineKeyboardButton("📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton("📬 Ulanyjylara habar", callback_data="adm_broadcast_users")],
        [InlineKeyboardButton("📡 Kanallara habar (bot admin)", callback_data="adm_broadcast_channels")],
        [InlineKeyboardButton("❌ Ýatyr", callback_data="adm_close")]
    ])
    if isinstance(trigger, Update):
        await trigger.message.reply_text("🛠️ Admin paneli:", reply_markup=kb)
    else:
        await trigger.edit_message_text("🛠️ Admin paneli:", reply_markup=kb)

async def admin_callbacks_dispatch(query, context: ContextTypes.DEFAULT_TYPE):
    data = query.data
    user = query.from_user

    if data == "adm_close":
        await query.edit_message_text("✅ Admin panelinden çykdyňyz.")
        return

    if data == "adm_channels":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Kanal goş", callback_data="adm_add_channel")],
            [InlineKeyboardButton("➖ Kanal poz", callback_data="adm_remove_channel")],
            [InlineKeyboardButton("📋 Kanal sanawy", callback_data="adm_list_channels")],
            [InlineKeyboardButton("⬅️ Artyka", callback_data="adm_open")]
        ])
        await query.edit_message_text("📢 Kanallar menýusy:", reply_markup=kb)
        return

    if data == "adm_vpns":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ VPN goş", callback_data="adm_add_vpn")],
            [InlineKeyboardButton("➖ VPN poz", callback_data="adm_remove_vpn")],
            [InlineKeyboardButton("📋 VPN sanawy", callback_data="adm_list_vpn")],
            [InlineKeyboardButton("⬅️ Artyka", callback_data="adm_open")]
        ])
        await query.edit_message_text("🔑 VPN kodlary menýusy:", reply_markup=kb)
        return

    if data == "adm_stats":
        users_count = db_execute("SELECT COUNT(*) FROM users", fetch=True)[0][0]
        ch_count = db_execute("SELECT COUNT(*) FROM channels", fetch=True)[0][0]
        vpn_count = db_execute("SELECT COUNT(*) FROM vpn_codes", fetch=True)[0][0]
        txt = f"📊 Statistika:\n• Ulanyjy sany: {users_count}\n• Kanal sany: {ch_count}\n• VPN kod sany: {vpn_count}"
        await query.edit_message_text(txt)
        return

    if data == "adm_broadcast_users":
        context.user_data["adm_action"] = "broadcast_users"
        await query.edit_message_text("✍️ Iltimas, ugratjak habaryňyzy şu hatarda ýazyp ugratma düwmesine basyň.")
        return

    if data == "adm_broadcast_channels":
        context.user_data["adm_action"] = "broadcast_channels"
        await query.edit_message_text("✍️ Kanallara ugratjak habaryňyzy şu hatarda ýazyp ugratma düwmesine basyň.")
        return

    # Channel submenu
    if data == "adm_add_channel":
        context.user_data["adm_action"] = "add_channel"
        await query.edit_message_text(
            "📥 Kanal goşmak üçin şu formatda ýazyň:\n\nlink|title|max_or_maxword|order_num|hours\n\n"
            "Meselem:\nhttps://t.me/mychannel|Meniň kanal|max|1|24"
        )
        return

    if data == "adm_remove_channel":
        context.user_data["adm_action"] = "remove_channel"
        await query.edit_message_text("📥 Kanal pozmak üçin: kanal ID-ni ýaz.") 
        return

    if data == "adm_list_channels":
        rows = db_execute("SELECT id,link,title,max_subs,order_num,show_until,bot_admin,subs_count FROM channels ORDER BY order_num ASC", fetch=True)
        if not rows:
            await query.edit_message_text("Kanal tapylmady.")
            return
        lines = ["📋 Kanal sanawy:"]
        for r in rows:
            cid, link, title, max_subs, order_num, show_until, bot_admin, subs_count = r
            max_text = "max" if (max_subs is None or max_subs == -1) else str(max_subs)
            until_text = datetime.utcfromtimestamp(show_until).isoformat() if show_until else "heç"
            lines.append(f"ID:{cid} | {title or link} | {link} | max:{max_text} | order:{order_num} | göst.:{until_text} | bot_admin:{bot_admin} | subs:{subs_count}")
        await query.edit_message_text("\n".join(lines))
        return

    # VPN submenu
    if data == "adm_add_vpn":
        context.user_data["adm_action"] = "add_vpn"
        await query.edit_message_text("📥 VPN kody (tekst) goşmak üçin kodu şu hatarda yaz.")
        return

    if data == "adm_remove_vpn":
        context.user_data["adm_action"] = "remove_vpn"
        await query.edit_message_text("📥 Pozmak isleýän VPN kodyň ID-sini ýaz.")
        return

    if data == "adm_list_vpn":
        rows = db_execute("SELECT id,text,sent_count,created_at FROM vpn_codes ORDER BY created_at DESC", fetch=True)
        if not rows:
            await query.edit_message_text("VPN kod tapylmady.")
            return
        lines = ["📦 VPN kodlar:"]
        for r in rows:
            vid, text, sent, created = r
            ts = datetime.utcfromtimestamp(created).isoformat()
            lines.append(f"ID:{vid} | sent:{sent} | created:{ts}\n{text}\n---")
        await query.edit_message_text("\n".join(lines))
        return

# ---------------- Admin text-actions ----------------
async def text_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return
    action = context.user_data.get("adm_action")
    if not action:
        return

    txt = update.message.text.strip()

    if action == "add_channel":
        parts = txt.split("|")
        if len(parts) < 5:
            await update.message.reply_text("Ulanylmasy dogry däl. Format: link|title|max_or_maxword|order_num|hours")
            context.user_data.pop("adm_action", None)
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
            show_until = 0
        db_execute("INSERT OR IGNORE INTO channels(link,title,max_subs,order_num,show_until) VALUES (?, ?, ?, ?, ?)",
                   (link, title, max_subs, order_num, show_until))
        # update bot_admin flag
        ba = 1 if await bot_is_admin_of(context.application, link) else 0
        db_execute("UPDATE channels SET bot_admin = ? WHERE link = ?", (ba, link))
        await update.message.reply_text(f"Kanal goşuldy: {title} ({link})\nBot admin status: {'Bar' if ba else 'Ýok'}")
        context.user_data.pop("adm_action", None)
        return

    if action == "remove_channel":
        try:
            cid = int(txt)
        except:
            await update.message.reply_text("Id san bolmaly.")
            context.user_data.pop("adm_action", None)
            return
        db_execute("DELETE FROM channels WHERE id = ?", (cid,))
        await update.message.reply_text(f"Kanal id={cid} pozuldy.")
        context.user_data.pop("adm_action", None)
        return

    if action == "add_vpn":
        db_execute("INSERT INTO vpn_codes(text) VALUES (?)", (txt,))
        await update.message.reply_text("✅ VPN kody goşuldy.")
        context.user_data.pop("adm_action", None)
        return

    if action == "remove_vpn":
        try:
            vid = int(txt)
        except:
            await update.message.reply_text("Id san bolmaly.")
            context.user_data.pop("adm_action", None)
            return
        db_execute("DELETE FROM vpn_codes WHERE id = ?", (vid,))
        await update.message.reply_text(f"VPN id={vid} pozuldy.")
        context.user_data.pop("adm_action", None)
        return

    if action == "broadcast_users":
        rows = db_execute("SELECT user_id FROM users", fetch=True)
        if not rows:
            await update.message.reply_text("Ulanyjy tapylmady.")
            context.user_data.pop("adm_action", None)
            return
        sent = 0
        for r in rows:
            uid = r[0]
            try:
                safe_msg = escape_html(txt)
                await context.bot.send_message(chat_id=uid, text=safe_msg, parse_mode=constants.ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning("broadcast to %s failed: %s", uid, e)
        await update.message.reply_text(f"Ugratdyldy: {sent} ulanyjyga.")
        context.user_data.pop("adm_action", None)
        return

    if action == "broadcast_channels":
        rows = db_execute("SELECT link FROM channels WHERE bot_admin = 1", fetch=True)
        if not rows:
            await update.message.reply_text("Bot admin bolmadyk kanal tapylmady.")
            context.user_data.pop("adm_action", None)
            return
        sent = 0
        for r in rows:
            link = r[0]
            try:
                safe_msg = escape_html(txt)
                await context.bot.send_message(chat_id=link, text=safe_msg, parse_mode=constants.ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning("broadcast channel %s failed: %s", link, e)
        await update.message.reply_text(f"Ugratdyldy: {sent} kanal/gruppe.")
        context.user_data.pop("adm_action", None)
        return

    # fallback
    await update.message.reply_text("Amal tamamlanmady. Iltimas, admin panelinden dolandyryň.")
    context.user_data.pop("adm_action", None)

# ---------------- Error handler ----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Exception in handler", exc_info=context.error)

# ---------------- Startup / Main ----------------
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    # One CallbackQueryHandler to dispatch all callbacks
    application.add_handler(CallbackQueryHandler(callback_dispatcher))
    # Admin entry
    application.add_handler(CommandHandler("admin", lambda u, c: show_admin_panel(u, c) if is_admin(u.effective_user.id) else None))
    # Admin text actions (channel add/remove, vpn add/remove, broadcasts)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_admin_action))
    # Error handler
    application.add_error_handler(error_handler)

    logger.info("Bot starting...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
