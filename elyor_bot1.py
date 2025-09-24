import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Ortamdan Token we Admin ID'leri al
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# SQLite baglanti
conn = sqlite3.connect("elyor_bot.db", check_same_thread=False)
cur = conn.cursor()

# Tablolar
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, max_subs TEXT, order_num INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS vpn_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, used_count INTEGER DEFAULT 0)")
conn.commit()

# /start komutu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cur.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (user.id, user.first_name))
    conn.commit()

    text = f"""👋 Salam {user.first_name}!

VPN kody almak üçin aşakdaky kanallara agza boluň
we soň '✅ Agza boldum' düwmesine basyň."""

    cur.execute("SELECT link FROM channels ORDER BY order_num ASC")
    channels = cur.fetchall()

    keyboard = []
    row = []
    for i, ch in enumerate(channels, start=1):
        row.append(InlineKeyboardButton(f"📢 Kanal {i}", url=ch[0]))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("✅ Agza boldum", callback_data="check_subscription")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Butonlary işledýän handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "check_subscription":
        cur.execute("SELECT code FROM vpn_codes LIMIT 1")
        code = cur.fetchone()
        if code:
            cur.execute("UPDATE vpn_codes SET used_count = used_count + 1 WHERE code = ?", (code[0],))
            conn.commit()
            await query.edit_message_text(f"🎉 Siz ähli kanallara agza boldunuz!\n\n🔑 VPN koduňyz: {code[0]}")
        else:
            await query.edit_message_text("⚠️ Häzirlikçe VPN kod ýok. Admin goşmaly.")

# Admin panel
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    text = """🔧 Admin paneline hoş geldiňiz!

/kanal_ekle link max order
/kanal_sil id
/kod_ekle KOD
/kodlar"""
    await update.message.reply_text(text)

# Kanal ekle
async def kanal_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        link = context.args[0]
        max_subs = context.args[1]
        order_num = int(context.args[2])
        cur.execute("INSERT INTO channels (link, max_subs, order_num) VALUES (?, ?, ?)", (link, max_subs, order_num))
        conn.commit()
        await update.message.reply_text("✅ Kanal goşuldy!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Näsazlyk: {e}")

# Kanal sil
async def kanal_sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        kanal_id = int(context.args[0])
        cur.execute("DELETE FROM channels WHERE id = ?", (kanal_id,))
        conn.commit()
        await update.message.reply_text("🗑️ Kanal aýryldy!")
    except:
        await update.message.reply_text("⚠️ ID nädogry.")

# VPN kod ekle
async def kod_ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        code = context.args[0]
        cur.execute("INSERT INTO vpn_codes (code) VALUES (?)", (code,))
        conn.commit()
        await update.message.reply_text("✅ VPN kody goşuldy!")
    except:
        await update.message.reply_text("⚠️ Kod nädogry.")

# VPN kodlary görkez
async def kodlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    cur.execute("SELECT code, used_count FROM vpn_codes")
    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("⚠️ Kod ýok.")
        return
    msg = "🔑 VPN Kodlar:\n"
    for r in rows:
        msg += f"{r[0]} → {r[1]} gezek ulanyldy\n"
    await update.message.reply_text(msg)

# Adaty tekst mesajlaryna jogap
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Men diňe görkezilen komandalar bilen işleýärin.")

# Ýalňyşlyklary loga ýaz
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Exception occurred:", exc_info=context.error)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Handler goşmak
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("kanal_ekle", kanal_ekle))
    application.add_handler(CommandHandler("kanal_sil", kanal_sil))
    application.add_handler(CommandHandler("kod_ekle", kod_ekle))
    application.add_handler(CommandHandler("kodlar", kodlar))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Botu başlatmak
    application.run_polling()

if __name__ == "__main__":
    main()
