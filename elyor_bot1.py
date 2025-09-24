import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ENV değişkenleri
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# -------- Kullanıcı Fonksiyonları -------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Salam {user.first_name}!\n\n"
        "🔑 VPN kody almak üçin aşakdaky kanallara agza boluň "
        "we soň aşakdaky düwmä basyň.\n"
    )
    keyboard = [
        [InlineKeyboardButton("📢 Kanal 1", url="https://t.me/example1"),
         InlineKeyboardButton("📢 Kanal 2", url="https://t.me/example2")],
        [InlineKeyboardButton("✅ Agza boldum", callback_data="check_subscription")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check_subscription":
        await query.edit_message_text(
            "🎉 Siz ähli kanallara agza boldunuz!\n\n🔑 VPN koduňyz: TEST-CODE-1234"
        )

    elif query.data == "admin_panel":
        await show_admin_panel(query, context)

    elif query.data == "stats":
        await query.edit_message_text("📊 Statistika: \n- Ulanyjylar: 123\n- Kanallar: 2")

    elif query.data == "send_message":
        context.user_data["waiting_broadcast"] = True
        await query.edit_message_text("✍️ Ulanyjylara ibermek üçin habaryňyzy ýazyp iberiň.")

    elif query.data == "cancel":
        await query.edit_message_text("❌ Amal ýatyryldy.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS and context.user_data.get("waiting_broadcast"):
        msg = update.message.text
        context.user_data["waiting_broadcast"] = False
        await update.message.reply_text("📨 Habar ähli ulanyjylara iberilýär... (Demo)")
        # Burada real database'e göre tüm kullanıcılara göndermek kodu gelir.


# -------- Admin Fonksiyonları -------- #
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await show_admin_panel(update, context)


async def show_admin_panel(update_or_query, context):
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("📨 Ulanyjylara habar", callback_data="send_message")],
        [InlineKeyboardButton("❌ Ýatyr", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if isinstance(update_or_query, Update):  # /admin komutu
        await update_or_query.message.reply_text("🔧 Admin paneli:", reply_markup=reply_markup)
    else:  # CallbackQuery
        await update_or_query.edit_message_text("🔧 Admin paneli:", reply_markup=reply_markup)


# -------- Error Logging -------- #
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Exception occurred:", exc_info=context.error)


# -------- Main -------- #
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
