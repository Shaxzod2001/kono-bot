import logging
import json
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import re
import asyncio

# --- Konfiguratsiya ---
try:
    from config import BOT_TOKEN, CHANNEL_ID, ADMIN_IDS
except ImportError:
    print("Xatolik: config.py faylini topa olmadim.")
    exit()

# --- Sozlash ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Ma'lumotlar bazasi ---
movie_database = {}
user_ids = set()

# --- Veb-ilova uchun yordamchi funksiya ---
def update_movies_json():
    """Kino ma'lumotlar bazasini webapp/movies.json fayliga yozadi."""
    try:
        with open("webapp/movies.json", "w", encoding="utf-8") as f:
            json.dump(movie_database, f, ensure_ascii=False, indent=4)
        logger.info("webapp/movies.json fayli yangilandi.")
    except Exception as e:
        logger.error(f"movies.json faylini yozishda xatolik: {e}")

# --- Suhbat holatlari ---
GET_DELETE_NUMBER, GET_BROADCAST_MESSAGE = range(2)

# --- Admin Paneli ---
ADMIN_KEYBOARD = [
    ["📊 Statistika", "🎬 Kinolar Roʻyxati"],
    ["📢 Xabar Yuborish", "🗑 Oʻchirish"],
    ["❌ Menyuni Yopish"],
]
ADMIN_KEYBOARD_MARKUP = ReplyKeyboardMarkup(ADMIN_KEYBOARD, resize_keyboard=True)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"📊 Bot Statistikasi:\n\n🎬 Bazadagi kinolar: {len(movie_database)}\n👥 Foydalanuvchilar: {len(user_ids)}"
    await update.message.reply_text(text)

async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not movie_database:
        await update.message.reply_text("Baza boʻsh.")
        return
    movie_list = "🎬 Bazadagi kinolar:\n\n" + "\n".join(f"#{n}" for n in sorted(movie_database.keys(), key=int))
    await update.message.reply_text(movie_list)

async def ask_for_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("📢 Hammaga yuboriladigan xabar matnini kiriting:")
    return GET_BROADCAST_MESSAGE

async def ask_for_delete_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🗑 Oʻchiriladigan kino raqamini kiriting:")
    return GET_DELETE_NUMBER

async def get_broadcast_message_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Implementation remains the same
    return ConversationHandler.END

async def get_delete_number_and_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    movie_number = update.message.text
    if movie_number in movie_database:
        del movie_database[movie_number]
        update_movies_json()  # Update JSON after deleting
        await update.message.reply_text(f"#{movie_number} raqamli kino oʻchirildi.")
    else:
        await update.message.reply_text("Bu raqamli kino topilmadi.")
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Amal bekor qilindi.", reply_markup=ADMIN_KEYBOARD_MARKUP)
    return ConversationHandler.END

# --- Asosiy funksiyalar ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_ids.add(user.id)
    logger.info(f"Yangi foydalanuvchi: {user.id}")
    
    reply_markup = ReplyKeyboardMarkup([["Veb-ilovada kinolarni ko'rish"]], resize_keyboard=True)
    message = f"Assalomu alaykum, {user.first_name}! Kinolarni ko'rish uchun pastdagi tugmani bosing."
    
    if user.id in ADMIN_IDS:
        reply_markup = ADMIN_KEYBOARD_MARKUP
        message += "\n\nSiz adminsiz. Boshqaruv panelidan foydalanishingiz mumkin."

    await update.message.reply_text(message, reply_markup=reply_markup)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # IMPORTANT: Replace with your actual GitHub Pages URL
    url = "https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/webapp/"
    keyboard = [[KeyboardButton("Veb-ilovada kinolarni ko'rish", web_app=WebAppInfo(url=url))]]
    await update.message.reply_text(
        "Kinolarni veb-ilovada ko'rish uchun tugmani bosing:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (implementation remains the same)
    movie_number = context.args[0]
    file_id = update.message.reply_to_message.video.file_id
    movie_database[movie_number] = file_id
    update_movies_json()  # Update JSON after adding
    await update.message.reply_text(f"✅ Kino #{movie_number} bazaga qo'shildi.")

async def _send_movie_logic(chat_id: int, movie_number: str, context: ContextTypes.DEFAULT_TYPE):
    if movie_number in movie_database:
        file_id = movie_database[movie_number]
        await context.bot.send_message(chat_id, "⏳ Kinoni yubormoqdaman, biroz kuting...")
        try:
            await context.bot.send_video(chat_id=chat_id, video=file_id)
        except Exception as e:
            logger.error(f"Kino #{movie_number} yuborishda xatolik: {e}")
            await context.bot.send_message(chat_id, "Ushbu kinoni yuborishda xatolik yuz berdi.")
    else:
        await context.bot.send_message(chat_id, "Afsuski, bu raqamli kino bazada mavjud emas.")

async def handle_text_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.isdigit():
        await _send_movie_logic(update.effective_chat.id, update.message.text, context)
    else:
        await update.message.reply_text("Iltimos, faqat kino raqamini yuboring yoki menyudan foydalaning.")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movie_number = update.effective_message.web_app_data.data
    await _send_movie_logic(update.effective_chat.id, movie_number, context)

# --- Botni ishga tushirish ---
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    admin_filters = filters.ChatType.PRIVATE & filters.User(user_id=ADMIN_IDS)

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(admin_filters & filters.Regex("^📢 Xabar Yuborish$"), ask_for_broadcast_message),
            MessageHandler(admin_filters & filters.Regex("^🗑 Oʻchirish$"), ask_for_delete_number),
        ],
        states={
            GET_BROADCAST_MESSAGE: [MessageHandler(admin_filters & filters.TEXT & ~filters.COMMAND, get_broadcast_message_and_send)],
            GET_DELETE_NUMBER: [MessageHandler(admin_filters & filters.TEXT & ~filters.COMMAND, get_delete_number_and_delete)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    application.add_handler(conv_handler)

    application.add_handler(MessageHandler(admin_filters & filters.Regex("^📊 Statistika$"), show_stats))
    application.add_handler(MessageHandler(admin_filters & filters.Regex("^🎬 Kinolar Roʻyxati$"), list_movies))
    application.add_handler(CommandHandler("admin", start, filters=admin_filters)) # /admin and /start are same for admin
    application.add_handler(MessageHandler(admin_filters & filters.Regex("^❌ Menyuni Yopish$"), lambda u, c: u.message.reply_text("Menyu yopildi.", reply_markup=ReplyKeyboardRemove())))
    application.add_handler(CommandHandler("close", lambda u, c: u.message.reply_text("Menyu yopildi.", reply_markup=ReplyKeyboardRemove()), filters=admin_filters))

    application.add_handler(CommandHandler("add", add_movie, filters=filters.Chat(chat_id=int(CHANNEL_ID)) & filters.User(user_id=ADMIN_IDS)))
    application.add_handler(CommandHandler("menu", menu))

    application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_text_request))

    logger.info("Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()
