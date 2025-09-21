import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

# --- Ayarlar ve ortam değişkenleri ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# --- Log (kayıt) ayarları ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SQLite veritabanı bağlantısı ---
conn = sqlite3.connect('sponsor_bot.db', check_same_thread=False)
cursor = conn.cursor()

# --- Tabloların oluşturulması ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL UNIQUE,
    channel_name TEXT NOT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS vpn_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    used INTEGER DEFAULT 0,
    user_id INTEGER DEFAULT NULL,
    used_date TEXT DEFAULT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_stats (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    joined_date TEXT,
    last_active TEXT
)
''')

conn.commit()

# --- Yardımcı fonksiyonlar ---
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# --- /start komutu ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute(
        "INSERT OR REPLACE INTO user_stats (user_id, username, first_name, last_name, joined_date, last_active) VALUES (?, ?, ?, ?, ?, ?)",
        (user.id, user.username, user.first_name, user.last_name,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    await update.message.reply_text(
        f"Salam {user.first_name}! 🎉\n\nBu bot sponsor dolandyryşy üçin ulanylýar. Komandalar üçin /admin ýazyň."
    )

# --- /admin komutu ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 Bu komanda diňe adminler üçin.")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("🔑 Kod Dolandyryşy", callback_data="code_menu")],
        [InlineKeyboardButton("📢 Kanal Dolandyryşy", callback_data="channel_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔐 Admin Paneli", reply_markup=reply_markup)

# --- Callback / Buton işleyici ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stats":
        cursor.execute("SELECT COUNT(*) FROM user_stats")
        user_count = cursor.fetchone()[0]
        await query.edit_message_text(f"📊 Jemi ulanyjy sany: {user_count}")

    elif query.data == "code_menu":
        keyboard = [
            [InlineKeyboardButton("➕ Kod Goş", callback_data="add_code")],
            [InlineKeyboardButton("📜 Kodlary Gör", callback_data="list_codes")],
            [InlineKeyboardButton("❌ Kod Poz", callback_data="delete_code")]
        ]
        await query.edit_message_text("🔑 Kod Dolandyryşy", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "add_code":
        context.user_data["mode"] = "add_code"
        await query.edit_message_text("Goşmak isleýän VPN kodyňyzy iberiň:")

    elif query.data == "list_codes":
        cursor.execute("SELECT code, used FROM vpn_codes")
        codes = cursor.fetchall()
        if not codes:
            await query.edit_message_text("Entäk ýazylan kod ýok.")
        else:
            text = "\n".join([f"{c[0]} - {'Ulanyldy' if c[1] else 'Ulanylmandy'}" for c in codes])
            await query.edit_message_text(f"📜 Ýazylan Kodlar:\n{text}")

    elif query.data == "delete_code":
        context.user_data["mode"] = "delete_code"
        await query.edit_message_text("Pozmak isleýän kodyňyzy iberiň:")

    elif query.data == "channel_menu":
        keyboard = [
            [InlineKeyboardButton("➕ Kanal Goş", callback_data="add_channel")],
            [InlineKeyboardButton("📜 Kanallary Gör", callback_data="list_channels")],
            [InlineKeyboardButton("❌ Kanal Poz", callback_data="delete_channel")]
        ]
        await query.edit_message_text("📢 Kanal Dolandyryşy", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "add_channel":
        context.user_data["mode"] = "add_channel"
        await query.edit_message_text("Täze kanal ID-si we adyny şu formatda iberiň:\n@kanal_id - Kanal Ady")

    elif query.data == "list_channels":
        cursor.execute("SELECT channel_id, channel_name FROM channels")
        chans = cursor.fetchall()
        if not chans:
            await query.edit_message_text("Entäk ýazylan kanal ýok.")
        else:
            text = "\n".join([f"{c[0]} - {c[1]}" for c in chans])
            await query.edit_message_text(f"📜 Ýazylan Kanallar:\n{text}")

    elif query.data == "delete_channel":
        context.user_data["mode"] = "delete_channel"
        await query.edit_message_text("Pozmak isleýän kanal ID-ňizi iberiň:")

# --- Mesaj işleyici ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message.text.strip()

    if is_admin(user.id) and "mode" in context.user_data:
        mode = context.user_data["mode"]

        if mode == "add_code":
            try:
                cursor.execute("INSERT INTO vpn_codes (code) VALUES (?)", (msg,))
                conn.commit()
                await update.message.reply_text("✅ Kod üstünlikli goşuldy.")
            except Exception as e:
                logger.exception("Kod goşulanda säwlik:")
                await update.message.reply_text("⚠️ Bu kod öňden bar ýa-da goşulanda säwlik boldy.")
            context.user_data.pop("mode", None)

        elif mode == "delete_code":
            cursor.execute("DELETE FROM vpn_codes WHERE code=?", (msg,))
            conn.commit()
            await update.message.reply_text("✅ Kod pozuldy (eger bar bolsa).")
            context.user_data.pop("mode", None)

        elif mode == "add_channel":
            try:
                if "-" in msg:
                    parts = msg.split("-", 1)
                    chan_id = parts[0].strip()
                    chan_name = parts[1].strip()
                    cursor.execute("INSERT INTO channels (channel_id, channel_name) VALUES (?, ?)", (chan_id, chan_name))
                    conn.commit()
                    await update.message.reply_text("✅ Kanal üstünlikli goşuldy.")
                else:
                    await update.message.reply_text("⚠️ Nädogry format. Şu görnüşde iberiň: @kanal_id - Kanal Ady")
            except Exception as e:
                logger.exception("Kanal goşulanda säwlik:")
                await update.message.reply_text("⚠️ Bu kanal öňden bar ýa-da goşulanda säwlik boldy.")
            context.user_data.pop("mode", None)

        elif mode == "delete_channel":
            cursor.execute("DELETE FROM channels WHERE channel_id=?", (msg,))
            conn.commit()
            await update.message.reply_text("✅ Kanal pozuldy (eger bar bolsa).")
            context.user_data.pop("mode", None)

        return

    cursor.execute("UPDATE user_stats SET last_active=? WHERE user_id=?", 
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user.id))
    conn.commit()

    await update.message.reply_text("Habaryňyz alyndy. Sag boluň! ✅")

# --- Hata işleyici ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ýalňyşlyk ýüze çykdy:", exc_info=context.error)

# --- Ana fonksiyon ---
def main():
    request = HTTPXRequest(http_version="1.1", connect_timeout=30, read_timeout=30)
    application = Application.builder().token(BOT_TOKEN).request(request).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
