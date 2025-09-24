import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
import os
import sqlite3

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DATABASE_PATH", "elyor.db")

# Database init
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS vpn_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        sent_count INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        link TEXT,
        max_subs TEXT DEFAULT "max"
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY
    )""")
    conn.commit()
    conn.close()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"👋 Salam {user.first_name}!\n\nVPN kody almak üçin aşakdaky kanallara agza boluň we soň aşakdaky '✅ Agza boldum' düwmesine basyň."
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT title, link FROM channels")
    channels = cur.fetchall()
    conn.close()

    keyboard = []
    for title, link in channels:
        keyboard.append([InlineKeyboardButton(f"📢 {title}", url=link)])
    keyboard.append([InlineKeyboardButton("✅ Agza boldum", callback_data="check_subscription")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Button
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "check_subscription":
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM vpn_codes ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            vpn_id, code = row
            cur.execute("UPDATE vpn_codes SET sent_count = sent_count + 1 WHERE id=?", (vpn_id,))
            conn.commit()
            await query.edit_message_text(f"🎉 Siz ähli kanallara agza boldunuz!\n\n🔑 VPN koduňyz: {code}")
        else:
            await query.edit_message_text("⚠️ Häzirlikçe VPN kod ýok.")
        conn.close()

# Admin
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    keyboard = [
        [InlineKeyboardButton("➕ Kanal goş", callback_data="add_channel"),
         InlineKeyboardButton("📋 Kanallary gör", callback_data="list_channels")],
        [InlineKeyboardButton("➕ VPN goş", callback_data="add_vpn"),
         InlineKeyboardButton("📋 VPN gör", callback_data="list_vpn")]
    ]
    await update.message.reply_text("🔧 Admin paneli", reply_markup=InlineKeyboardMarkup(keyboard))

# Normal messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Men diňe görkezilen komandalar bilen işleýärin.")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Exception occurred:", exc_info=context.error)

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
