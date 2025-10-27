import logging
import json
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

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

# --- Ma'lumotlar bazasi (fayllarda saqlanadi) ---
MOVIE_DB_FILE = "webapp/movies.json"
USER_DB_FILE = "data/users.json"
movie_database = {}
user_ids = set()

# --- Git Avtomatizatsiyasi ---
async def git_push_updates(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """O'zgarishlarni avtomatik GitHub'ga yuklaydi."""
    await context.bot.send_message(chat_id=chat_id, text="🔄 Oʻzgarishlar GitHubʻga yuklanmoqda...")
    try:
        # Using os.system for simplicity as run_shell_command is not available in this context
        os.system('git add webapp/movies.json data/users.json')
        # Commit only if there are changes
        if os.system('git diff --quiet --exit-code --cached') != 0:
            os.system('git commit -m "[Bot] Auto-update data"')
            push_result = os.system("git push origin main")
            if push_result == 0:
                await context.bot.send_message(chat_id=chat_id, text="✅ Oʻzgarishlar GitHubʻga muvaffaqiyatli yuklandi!")
            else:
                await context.bot.send_message(chat_id=chat_id, text="❌ GitHubʻga yuklashda xatolik yuz berdi.")
        else:
            await context.bot.send_message(chat_id=chat_id, text="ℹ️ Yuklash uchun yangi oʻzgarishlar yoʻq.")

    except Exception as e:
        logger.error(f"Git push xatoligi: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ GitHubʻga yuklashda kutilmagan xatolik: {e}")

# --- Ma'lumotlarni Saqlash/Yuklash ---
def load_data():
    global movie_database, user_ids
    try:
        with open(MOVIE_DB_FILE, "r") as f: movie_database = json.load(f)
        logger.info(f"{len(movie_database)} ta kino yuklandi.")
    except (FileNotFoundError, json.JSONDecodeError): update_movies_json()
    try:
        with open(USER_DB_FILE, "r") as f: user_ids = set(json.load(f))
        logger.info(f"{len(user_ids)} ta foydalanuvchi yuklandi.")
    except (FileNotFoundError, json.JSONDecodeError): save_user_ids()

def update_movies_json():
    with open(MOVIE_DB_FILE, "w") as f: json.dump(movie_database, f, indent=4)
    logger.info(f"{MOVIE_DB_FILE} yangilandi.")

def save_user_ids():
    with open(USER_DB_FILE, "w") as f: json.dump(list(user_ids), f)
    logger.info(f"{USER_DB_FILE} yangilandi.")

# --- Suhbat holatlari ---
GET_DELETE_NUMBER, GET_BROADCAST_MESSAGE = range(2)

# --- Admin Paneli ---
ADMIN_KEYBOARD = [["📊 Statistika", "🎬 Kinolar Roʻyxati"], ["📢 Xabar Yuborish", "🗑 Oʻchirish"], ["❌ Menyuni Yopish"]]
ADMIN_KEYBOARD_MARKUP = ReplyKeyboardMarkup(ADMIN_KEYBOARD, resize_keyboard=True)

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Bot Statistikasi:\n\n🎬 Bazadagi kinolar: {len(movie_database)}\n👥 Foydalanuvchilar: {len(user_ids)}")

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
    message_to_send = update.message.text
    sent_count = 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_send)
            sent_count += 1
            await asyncio.sleep(0.1)
        except Exception: pass
    await update.message.reply_text(f"Xabar {sent_count} ta foydalanuvchiga yuborildi.")
    return ConversationHandler.END

async def get_delete_number_and_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    movie_number = update.message.text
    if movie_number in movie_database:
        del movie_database[movie_number]
        update_movies_json()
        await update.message.reply_text(f"#{movie_number} raqamli kino oʻchirildi.")
        await git_push_updates(context, update.effective_chat.id)
    else:
        await update.message.reply_text("Bu raqamli kino topilmadi.")
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Amal bekor qilindi.", reply_markup=ADMIN_KEYBOARD_MARKUP)
    return ConversationHandler.END

# --- Asosiy funksiyalar ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in user_ids:
        user_ids.add(user.id)
        save_user_ids()
        logger.info(f"Yangi foydalanuvchi: {user.id}")
    
    message = f"Assalomu alaykum, {user.first_name}! "
    if user.id in ADMIN_IDS:
        reply_markup = ADMIN_KEYBOARD_MARKUP
        message += "Siz adminsiz. Boshqaruv panelidan foydalanishingiz mumkin."
    else:
        web_app_url = "https://shaxzod2001.github.io/kono-bot/webapp/"
        web_app_button = KeyboardButton("🎬 Kinolarni ko'rish (Veb)", web_app=WebAppInfo(url=web_app_url))
        reply_markup = ReplyKeyboardMarkup([[web_app_button]], resize_keyboard=True)
        message += "Kinolarni veb-ilovada ko'rish uchun pastdagi tugmani bosing."
    await update.message.reply_text(message, reply_markup=reply_markup)

async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        await update.message.reply_text("Bu buyruqni video xabarga javob (reply) sifatida yuboring.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Kino raqamini kiriting. Masalan: /add 125")
        return

    movie_number = context.args[0]
    file_id = update.message.reply_to_message.video.file_id
    movie_database[movie_number] = file_id
    update_movies_json()
    await update.message.reply_text(f"✅ Kino #{movie_number} bazaga qo'shildi.")
    await git_push_updates(context, update.effective_chat.id)

async def _send_movie_logic(chat_id: int, movie_number: str, context: ContextTypes.DEFAULT_TYPE):
    if movie_number in movie_database:
        file_id = movie_database[movie_number]
        await context.bot.send_message(chat_id, "⏳ Kinoni yubormoqdaman...")
        try: await context.bot.send_video(chat_id=chat_id, video=file_id)
        except Exception as e: await context.bot.send_message(chat_id, "Bu kinoni yuborishda xatolik.")
    else:
        await context.bot.send_message(chat_id, "Afsuski, bu raqamli kino yoʻq.")

async def handle_text_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.isdigit():
        await _send_movie_logic(update.effective_chat.id, update.message.text, context)
    else:
        await update.message.reply_text("Iltimos, kino raqamini yuboring yoki menyudan foydalaning.")

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movie_number = update.effective_message.web_app_data.data
    await _send_movie_logic(update.effective_chat.id, movie_number, context)

# --- Botni ishga tushirish ---
def main():
    load_data()
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
    application.add_handler(CommandHandler("admin", start, filters=admin_filters))
    application.add_handler(MessageHandler(admin_filters & filters.Regex("^❌ Menyuni Yopish$"), lambda u, c: u.message.reply_text("Menyu yopildi.", reply_markup=ReplyKeyboardRemove())))
    application.add_handler(CommandHandler("close", lambda u, c: u.message.reply_text("Menyu yopildi.", reply_markup=ReplyKeyboardRemove()), filters=admin_filters))
    application.add_handler(CommandHandler("add", add_movie, filters=filters.Chat(chat_id=int(CHANNEL_ID)) & filters.User(user_id=ADMIN_IDS)))
    application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_text_request))

    logger.info("Bot ishga tushdi...")
    application.run_polling()

if __name__ == "__main__":
    main()