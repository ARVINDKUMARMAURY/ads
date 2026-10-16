import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import requests
import urllib.parse
import uuid
import time

# ================= 1. APNI DETAILS YAHAN DAALEIN =================
BOT_TOKEN = "8656616546:AAGeo4elsHy4VoUKxCZB6tj3EzUigXi4dsk"          # Apna Telegram Bot Token daalein
ADMIN_ID = 8263530800                           # Apna Telegram User ID daalein (bina quotes ke)
GPLINKS_API_TOKEN = "2a064f39d8934a6ea4fac4df56d8a7a57c55f64d"   # Apna GPLinks API Token daalein

# MongoDB Connection URL (mongodb.com se apna cluster URI yahan paste karein)
MONGO_URI = "mongodb+srv://yb131567_db_user:R8zxuvc9Qn999Arg@cluster0.drjaxl8.mongodb.net/telegram_ads?retryWrites=true&w=majority"

ONLY_ADMIN_UPLOAD = True

# ================= 2. MONGODB DATABASE SETUP =================
bot = telebot.TeleBot(BOT_TOKEN)

try:
    client = MongoClient(MONGO_URI)
    db = client["TelegramEarningBot"]
    files_col = db["files"]   # Files save karne ke liye collection
    users_col = db["users"]   # Users save karne ke liye collection (Broadcast ke liye)
    print("✅ MongoDB Successfully Connected!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# User ko database mein save karne ka function
def add_user_to_db(user_id, first_name):
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({
            "user_id": user_id,
            "name": first_name,
            "joined_at": int(time.time())
        })

# ================= 3. GPLINKS API FUNCTION =================
def shorten_url_gplinks(long_url):
    encoded_url = urllib.parse.quote(long_url)
    endpoints = [
        f"https://api.gplinks.com/api?api={GPLINKS_API_TOKEN}&url={encoded_url}",
        f"https://gplinks.in/api?api={GPLINKS_API_TOKEN}&url={encoded_url}"
    ]
    
    for api_url in endpoints:
        try:
            response = requests.get(api_url, timeout=10)
            data = response.json()
            if data.get("status") == "success" and data.get("shortenedUrl"):
                return data["shortenedUrl"].replace("\\/", "/")
        except Exception as e:
            print(f"API Error: {e}")
            
    return long_url

# ================= 4. ADMIN STATS & BROADCAST COMMANDS =================

# 📊 /stats - Total Users aur Total Files dekhne ke liye
@bot.message_handler(commands=['stats'])
def bot_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    total_users = users_col.count_documents({})
    total_files = files_col.count_documents({})
    
    stats_text = (
        "📊 *Bot Live Statistics (MongoDB)* 📊\n\n"
        f"👥 *Total Registered Users:* `{total_users}`\n"
        f"📁 *Total Uploaded Files:* `{total_files}`\n\n"
        "💡 *Tip:* Kisi bhi message par reply karke `/broadcast` likhein sabhi users ko message bhejne ke liye."
    )
    bot.reply_to(message, stats_text, parse_mode="Markdown")

# 📢 /broadcast - Sabhi users ko message/photo/video bhejne ke liye
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        return

    # Check karein ki Admin ne kisi message par reply kiya hai ya nahi
    if not message.reply_to_message:
        bot.reply_to(
            message,
            "⚠️ *Broadcast kaise karein?*\n\n"
            "Pehle bot mein koi bhi Text, Photo, ya Video bhejein, phir us message par **Reply** karte hue `/broadcast` likhein!",
            parse_mode="Markdown"
        )
        return

    all_users = list(users_col.find({}))
    total = len(all_users)
    sent = 0
    failed = 0

    status_msg = bot.reply_to(message, f"🚀 *Broadcast shuru ho raha hai...*\nTotal Users: `{total}`", parse_mode="Markdown")

    for user in all_users:
        uid = user["user_id"]
        try:
            # copy_message se Text, Photo, Video, Button sab kuch as-it-is jata hai
            bot.copy_message(
                chat_id=uid,
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            sent += 1
            time.sleep(0.05)  # Telegram flood limit se bachne ke liye chota pause
        except Exception:
            failed += 1

    bot.edit_message_text(
        f"✅ *Broadcast Completed!*\n\n"
        f"👥 *Total Users:* `{total}`\n"
        f"📩 *Successfully Sent:* `{sent}`\n"
        f"🚫 *Failed / Blocked Bot:* `{failed}`",
        message.chat.id,
        status_msg.message_id,
        parse_mode="Markdown"
    )

# ================= 5. START & FILE DELIVERY HANDLER =================
@bot.message_handler(commands=['start'])
def start_command(message):
    # User ko MongoDB mein save karna
    add_user_to_db(message.from_user.id, message.from_user.first_name)
    
    args = message.text.split()
    
    if len(args) > 1:
        token = args[1]
        
        # Step A: User channel link se aaya -> GPLinks generate karna
        if token.startswith("get_"):
            file_key = token.replace("get_", "")
            file_doc = files_col.find_one({"file_key": file_key})
            
            if file_doc:
                bot_username = bot.get_me().username
                final_delivery_link = f"https://t.me/{bot_username}?start=deliver_{file_key}"
                
                wait_msg = bot.reply_to(
                    message,
                    "⏳ *Aapka Download Link generate ho raha hai, kripya 2 second rukein...*",
                    parse_mode="Markdown"
                )
                
                paid_short_link = shorten_url_gplinks(final_delivery_link)
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔓 Unlock & Download File", url=paid_short_link))
                
                bot.edit_message_text(
                    "📁 *Aapki File Ready Hai!*\n\n"
                    "👇 File prapt karne ke liye niche **'Unlock & Download File'** button par click karein:",
                    message.chat.id,
                    wait_msg.message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            else:
                bot.reply_to(message, "❌ Yeh file link expire ho chuka hai ya galat hai.")
            return

        # Step B: User GPLinks verify karke aaya -> Asli File bhejna
        elif token.startswith("deliver_"):
            file_key = token.replace("deliver_", "")
            file_doc = files_col.find_one({"file_key": file_key})
            
            if file_doc:
                file_id = file_doc["file_id"]
                file_type = file_doc["type"]
                caption = file_doc.get("caption", "🎉 Here is your file!")

                bot.send_message(
                    message.chat.id,
                    "✅ *Verification Successful! Aapki file niche bheji ja rahi hai...*",
                    parse_mode="Markdown"
                )
                
                if file_type == "document":
                    bot.send_document(message.chat.id, file_id, caption=caption)
                elif file_type == "video":
                    bot.send_video(message.chat.id, file_id, caption=caption)
                elif file_type == "audio":
                    bot.send_audio(message.chat.id, file_id, caption=caption)
                elif file_type == "photo":
                    bot.send_photo(message.chat.id, file_id, caption=caption)
            else:
                bot.reply_to(message, "❌ File database mein nahi mili!")
            return

    # Normal /start message
    welcome_msg = (
        f"👋 *Namaste {message.from_user.first_name}!*\n\n"
        "📦 Main **GPLinks Monetized File Bot** hoon.\n\n"
        "• Channel par diye gaye links par click karke apni manpasand files download karein!"
    )
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")

# ================= 6. FILE UPLOAD HANDLER (MONGODB) =================
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
    
    # MongoDB mein file save karna
    files_col.insert_one({
        "file_key": unique_key,
        "file_id": file_id,
        "type": f_type,
        "caption": message.caption or f"📁 {f_name}",
        "created_at": int(time.time())
    })

    bot_username = bot.get_me().username
    shareable_bot_link = f"https://t.me/{bot_username}?start=get_{unique_key}"

    reply_text = (
        f"✅ *File Saved in MongoDB & Linked with GPLinks!*\n\n"
        f"📄 *File Name:* `{f_name}`\n\n"
        f"🔗 *Aapka Channel Link (Ise share karein):*\n"
        f"`{shareable_bot_link}`"
    )
    bot.reply_to(message, reply_text, parse_mode="Markdown")

# ================= 7. DIRECT LINK SHORTENER =================
@bot.message_handler(func=lambda msg: msg.text and ("http://" in msg.text or "https://" in msg.text))
def handle_links(message):
    if ONLY_ADMIN_UPLOAD and message.from_user.id != ADMIN_ID:
        return

    wait = bot.reply_to(message, "🔗 *GPLinks se link short kiya ja raha hai...*", parse_mode="Markdown")
    short_link = shorten_url_gplinks(message.text.strip())
    
    bot.edit_message_text(
        f"✅ *Aapka GPLinks Short Link Taiyar Hai:*\n\n`{short_link}`",
        message.chat.id,
        wait.message_id,
        parse_mode="Markdown"
    )

print("🚀 GPLinks + MongoDB + Broadcast Bot chalu ho gaya hai...")
bot.infinity_polling()
