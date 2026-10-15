import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import os
import urllib.parse
import uuid

# ================= CONFIGURATION =================
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Yahan apna BotFather token daalein
ADMIN_ID = 123456789                   # Apna Telegram User ID daalein

# ShrinkMe.io API Credentials (jo aapne provide ki hain)
SHRINKME_API_TOKEN = "d4873836d6d609b9ddf431bb52dbece0aa0891c5"
SHRINKME_DOMAIN = "shrinkme.io"

ONLY_ADMIN_UPLOAD = True

bot = telebot.TeleBot(BOT_TOKEN)
FILES_DB = "files_data.json"

# ================= DATABASE SETUP =================
def load_files():
    if os.path.exists(FILES_DB):
        with open(FILES_DB, "r") as f:
            return json.load(f)
    return {}

def save_files(data):
    with open(FILES_DB, "w") as f:
        json.dump(data, f, indent=4)

# ================= SHRINKME API FUNCTION =================
def shorten_url_shrinkme(long_url):
    # URL encode karna zaroori hai
    encoded_long_url = urllib.parse.quote(long_url)
    api_url = f"https://{SHRINKME_DOMAIN}/api?api={SHRINKME_API_TOKEN}&url={encoded_long_url}&format=text"
    
    try:
        response = requests.get(api_url, timeout=10)
        short_link = response.text.strip()
        
        # Agar API ne valid link diya hai
        if short_link.startswith("http"):
            return short_link
    except Exception as e:
        print(f"ShrinkMe API Error: {e}")
    
    # Agar API fail ho jaye toh fallback ke taur par original link return karega
    return long_url

# ================= START & FILE DELIVERY HANDLER =================
@bot.message_handler(commands=['start'])
def start_command(message):
    args = message.text.split()
    
    if len(args) > 1:
        token = args[1]
        files_db = load_files()
        
        # 1. Jab user Shortener Link par click karke bot par aaye
        if token.startswith("get_"):
            file_key = token.replace("get_", "")
            if file_key in files_db:
                bot_username = bot.get_me().username
                # Final link jo ad dekhne ke baad khulega
                final_delivery_link = f"https://t.me/{bot_username}?start=deliver_{file_key}"
                
                wait_msg = bot.reply_to(message, "⏳ *ShrinkMe API se earning link taiyar kiya ja raha hai...*", parse_mode="Markdown")
                
                # Yahan ShrinkMe API call hogi
                paid_short_link = shorten_url_shrinkme(final_delivery_link)
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔓 Unlock & Download File", url=paid_short_link))
                markup.add(InlineKeyboardButton("❓ How to Download (Tutorial)", url="https://t.me/YourTutorialChannel"))
                
                bot.edit_message_text(
                    "📁 *Aapki File Ready Hai!*\n\n"
                    "👇 File prapt karne ke liye niche **'Unlock & Download File'** button par click karein aur process pura karein:",
                    message.chat.id,
                    wait_msg.message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            else:
                bot.reply_to(message, "❌ Yeh file link expire ho chuka hai ya galat hai.")
            return

        # 2. Verification ke baad asli file bhejna
        elif token.startswith("deliver_"):
            file_key = token.replace("deliver_", "")
            if file_key in files_db:
                file_info = files_db[file_key]
                file_id = file_info["file_id"]
                file_type = file_info["type"]
                caption = file_info.get("caption", "🎉 Here is your requested file!")

                bot.send_message(message.chat.id, "✅ *Verification Successful! Aapki file bheji ja rahi hai...*", parse_mode="Markdown")
                
                if file_type == "document":
                    bot.send_document(message.chat.id, file_id, caption=caption)
                elif file_type == "video":
                    bot.send_video(message.chat.id, file_id, caption=caption)
                elif file_type == "audio":
                    bot.send_audio(message.chat.id, file_id, caption=caption)
                elif file_type == "photo":
                    bot.send_photo(message.chat.id, file_id, caption=caption)
            else:
                bot.reply_to(message, "❌ File nahi mili!")
            return

    # Normal /start message
    welcome_msg = (
        f"👋 *Namaste {message.from_user.first_name}!*\n\n"
        "📦 Main ek **ShrinkMe Monetized File Bot** hoon.\n\n"
        "• Mujhe koi bhi Video, PDF, ya Document bhejein, main turant uska **ShrinkMe Earning Link** bana dunga!"
    )
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

# ================= FILE UPLOAD HANDLER (FOR ADMIN) =================
@bot.message_handler(content_types=['document', 'video', 'audio', 'photo'])
def handle_files(message):
    if ONLY_ADMIN_UPLOAD and message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Sirf Bot Admin hi files upload kar sakte hain!")
        return

    if message.document:
        file_id = message.document.file_id
        f_type = "document"
        f_name = message.document.file_name
    elif message.video:
        file_id = message.video.file_id
        f_type = "video"
        f_name = message.video.file_name or "Video File"
    elif message.audio:
        file_id = message.audio.file_id
        f_type = "audio"
        f_name = message.audio.title or "Audio File"
    elif message.photo:
        file_id = message.photo[-1].file_id
        f_type = "photo"
        f_name = "Photo"

    unique_key = str(uuid.uuid4())[:8]
    files_db = load_files()
    
    files_db[unique_key] = {
        "file_id": file_id,
        "type": f_type,
        "caption": message.caption or f"📁 *{f_name}*"
    }
    save_files(files_db)

    bot_username = bot.get_me().username
    shareable_bot_link = f"https://t.me/{bot_username}?start=get_{unique_key}"

    reply_text = (
        f"✅ *File Successfully Saved & Linked with ShrinkMe!* \n\n"
        f"📄 *File Name:* `{f_name}`\n\n"
        f"🔗 *Aapka Channel Link (Ise channel par share karein):*\n"
        f"`{shareable_bot_link}`"
    )
    bot.reply_to(message, reply_text, parse_mode="Markdown")

# ================= TEXT LINK SHORTENER =================
@bot.message_handler(func=lambda msg: msg.text and ("http://" in msg.text or "https://" in msg.text))
def handle_links(message):
    if ONLY_ADMIN_UPLOAD and message.from_user.id != ADMIN_ID:
        return

    wait = bot.reply_to(message, "🔗 *ShrinkMe API ke zariye link short kiya ja raha hai...*", parse_mode="Markdown")
    short_link = shorten_url_shrinkme(message.text.strip())
    
    bot.edit_message_text(
        f"✅ *Aapka ShrinkMe Short Link Taiyar Hai:*\n\n`{short_link}`",
        message.chat.id,
        wait.message_id,
        parse_mode="Markdown"
    )

print("🚀 ShrinkMe Earning Bot chalu ho gaya hai...")
bot.infinity_polling()
