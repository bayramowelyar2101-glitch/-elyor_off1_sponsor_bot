import os
import logging
import sqlite3
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import TelegramError
from telegram.request import HTTPXRequest

# Token ve Admin ID'lerini Railway ENV'den oku
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# Loglama ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Veritabanı bağlantısı
conn = sqlite3.connect('sponsor_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Tabloları oluştur
cursor.execute('''
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL UNIQUE,
    channel_name TEXT NOT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL UNIQUE
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


# Yardımcı fonksiyonlar
def is_admin(user_id):
    return user_id in ADMIN_IDS

# (Kısaltma: Fonksiyonların geri kalanı senin mevcut kodundaki gibi kalıyor...)
# Burada sadece main() kısmını güncelledim.

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception occurred:", exc_info=context.error)


def main():
    # HTTPX ayarları
    request = HTTPXRequest(http_version="1.1", connect_timeout=30, read_timeout=30)

    # Bot uygulamasını oluştur
    application = Application.builder().token(BOT_TOKEN).request(request).build()

    # Handler'ları ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Botu başlat
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
