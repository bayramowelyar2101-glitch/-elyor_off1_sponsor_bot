import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import os

# Logging ayarı
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Ortam değişkenleri
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# /start komutu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Salam {user.first_name}!

"
        "VPN kody almak üçin aşakdaky kanallara agza boluň "
        "we soň '✅ Agza boldum' düwmesine basyň."
    )
    keyboard = [
        [InlineKeyboardButton("📢 Kanal 1", url="https://t.me/example1"),
         InlineKeyboardButton("📢 Kanal 2", url="https://t.me/example2")],
        [InlineKeyboardButton("✅ Agza boldum", callback_data="check_subscription")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Buton işleyici
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "check_subscription":
        await query.edit_message_text(
            "🎉 Siz ähli kanallara agza boldunuz!

🔑 VPN koduňyz: TEST-CODE-1234"
        )

# Admin panel
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("🔧 Admin paneline hoş geldiňiz!")

# Mesaj işleyici
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Men diňe görkezilen komandalar bilen işleýärin.")

# Hata işleyici
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Exception occurred:", exc_info=context.error)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
