import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import requests
import urllib.parse
import uuid
import time
import os

# ================= 1. YOUR EXACT CREDENTIALS (ALL SET) =================
BOT_TOKEN = "8748128952:AAHLm6DrtbolX5K9eVFyWS5U4GgmdvJBYOU"
MONGO_URI = "mongodb+srv://yb131567_db_user:R8zxuvc9Qn999Arg@cluster0.drjaxl8.mongodb.net/telegram_ads?retryWrites=true&w=majority"
GPLINKS_API_TOKEN = "2a064f39d8934a6ea4fac4df56d8a7a57c55f64d"
ADMIN_ID = 8263530800  # Aapki exact Admin ID lock kar di gayi hai

# ================= 2. BOT & MONGODB CONNECTION =================
bot = telebot.TeleBot(BOT_TOKEN)

files_col = None
users_col = None
MEM_FILES = {}  # Memory backup taaki MongoDB slow hone par bhi file turant mile

try:
    # 5-second timeout taaki bot kabhi freeze/hang na ho
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client["telegram_ads"]
    files_col = db["files"]
    users_col = db["users"]
    print("✅ MongoDB Connected Successfully to 'telegram_ads'!")
except Exception as e:
    print(f"❌ MongoDB Setup Error: {e}")

def add_user_to_db(user_id, first_name):
    if users_col is not None:
        try:
            if not users_col.find_one({"user_id": user_id}):
                users_col.insert_one({
                    "user_id": user_id,
                    "name": first_name,
                    "joined_at": int(time.time())
                })
        except Exception as e:
            print(f"⚠️ MongoDB User Save Error (Allow 0.0.0.0/0 in Atlas): {e}")

# ================= 3. ONLY GPLINKS SHORTENER =================
def shorten_url_gplinks(long_url):
    encoded_url = urllib.parse.quote(long_url)
    
    gp_endpoints = [
        f"https://api.gplinks.com/api?api={GPLINKS_API_TOKEN}&url={encoded_url}",
        f"https://gplinks.in/api?api={GPLINKS_API_TOKEN}&url={encoded_url}"
    ]
    for api_url in gp_endpoints:
        try:
            res = requests.get(api_url, timeout=8).json()
            if res.get("status") == "success" and res.get("shortenedUrl"):
                return res["shortenedUrl"].replace("\\/", "/")
        except Exception as e:
            print(f"GPLinks Attempt Error: {e}")

    return long_url

# ================= 4. START & FILE DELIVERY HANDLER =================
@bot.message_handler(commands=['start'])
def start_command(message):
    args = message.text.split()
    
    # Agar user file link par click karke aaya hai
    if len(args) > 1:
        token = args[1]
        
        # Step A: User ko GPLinks Unlock Button dena
        if token.startswith("get_"):
            file_key = token.replace("get_", "")
            file_doc = MEM_FILES.get(file_key)
            
            if not file_doc and files_col is not None:
                try:
                    file_doc = files_col.find_one({"file_key": file_key})
                except Exception as e:
                    print(f"MongoDB Read Error: {e}")

            if file_doc:
                bot_username = bot.get_me().username
                final_delivery_link = f"https://t.me/{bot_username}?start=deliver_{file_key}"
                
                wait_msg = bot.reply_to(
                    message,
                    "⏳ *GPLinks se aapka Download Link ban raha hai, 2 second rukein...*",
                    parse_mode="Markdown"
                )
                
                paid_short_link = shorten_url_gplinks(final_delivery_link)
                
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔓 Unlock & Download File", url=paid_short_link))
                
                bot.edit_message_text(
                    "📁 *Aapki File Ready Hai!*\n\n"
                    "👇 File download karne ke liye niche **'Unlock & Download File'** button par click karein:",
                    message.chat.id,
                    wait_msg.message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            else:
                bot.reply_to(message, "❌ Yeh file link expire ho chuka hai ya database mein nahi mila.")
            
            add_user_to_db(message.from_user.id, message.from_user.first_name)
            return

        # Step B: GPLinks verify karne ke baad Asli File bhejna
        elif token.startswith("deliver_"):
            file_key = token.replace("deliver_", "")
            file_doc = MEM_FILES.get(file_key)
            
            if not file_doc and files_col is not None:
                try:
                    file_doc = files_col.find_one({"file_key": file_key})
                except Exception:
                    pass

            if file_doc:
                f_type = file_doc["type"]
                f_id = file_doc["file_id"]
                cap = file_doc.get("caption", "🎉 Here is your requested file!")
                
                bot.send_message(message.chat.id, "✅ *Verification Successful! Aapki file bheji ja rahi hai...*", parse_mode="Markdown")
                if f_type == "document": bot.send_document(message.chat.id, f_id, caption=cap)
                elif f_type == "video": bot.send_video(message.chat.id, f_id, caption=cap)
                elif f_type == "audio": bot.send_audio(message.chat.id, f_id, caption=cap)
                elif f_type == "photo": bot.send_photo(message.chat.id, f_id, caption=cap)
            else:
                bot.reply_to(message, "❌ File nahi mili!")
            return

    # Admin aur Normal User ke liye alag-alag Welcome Message
    if message.from_user.id == ADMIN_ID:
        welcome_msg = (
            f"👑 *Welcome Admin ({message.from_user.first_name})!*\n\n"
            f"📦 Aapka **GPLinks + MongoDB Bot** active hai.\n\n"
            f"• Koi bhi **File/Video/PDF/Photo** bhejein earning link banane ke liye.\n"
            f"• Live Stats dekhein: `/stats`\n"
            f"• Sabhi users ko message bhejein: Kisi message par reply karke `/broadcast` likhein."
        )
    else:
        welcome_msg = (
            f"👋 *Namaste {message.from_user.first_name}!*\n\n"
            f"📦 Main **File Sharing Bot** hoon.\n"
            f"Hamare channel par diye gaye links par click karke apni files download karein!"
        )
        
    bot.reply_to(message, welcome_msg, parse_mode="Markdown")
    add_user_to_db(message.from_user.id, message.from_user.first_name)

# ================= 5. /stats & /broadcast COMMANDS (ONLY FOR ADMIN) =================
@bot.message_handler(commands=['stats'])
def bot_stats(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Yeh command sirf Bot Admin ke liye hai!")
        return

    try:
        total_users = users_col.count_documents({}) if users_col is not None else 0
        total_files = files_col.count_documents({}) if files_col is not None else len(MEM_FILES)
        
        stats_text = (
            "📊 *Bot Live Statistics (MongoDB)* 📊\n\n"
            f"👥 *Total Registered Users:* `{total_users}`\n"
            f"📁 *Total Uploaded Files:* `{total_files}`\n"
            f"👑 *Admin ID:* `{ADMIN_ID}`"
        )
        bot.reply_to(message, stats_text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(
            message,
            f"⚠️ *MongoDB Network Access Block Hai!*\nError: `{e}`\n\n"
            f"👉 *Solution:* MongoDB Atlas kholein -> **Network Access** -> **Add IP Address** -> `0.0.0.0/0` (Allow Access from Anywhere) save karein!",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Sirf Admin broadcast kar sakta hai!")
        return

    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ Kisi message, photo ya video par **Reply** karte hue `/broadcast` likhein!", parse_mode="Markdown")
        return

    try:
        all_users = list(users_col.find({})) if users_col is not None else []
    except Exception as e:
        bot.reply_to(message, f"❌ Database Error: {e}")
        return

    total = len(all_users)
    sent = 0
    failed = 0
    status_msg = bot.reply_to(message, f"🚀 *Broadcast shuru ho raha hai...*\nTotal Users: `{total}`", parse_mode="Markdown")

    for user in all_users:
        try:
            bot.copy_message(
                chat_id=user["user_id"],
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            sent += 1
            time.sleep(0.05)
        except Exception:
            failed += 1

    bot.edit_message_text(
        f"✅ *Broadcast Completed!*\n\n👥 Total Users: `{total}`\n📩 Sent: `{sent}`\n🚫 Failed: `{failed}`",
        message.chat.id,
        status_msg.message_id,
        parse_mode="Markdown"
    )

# ================= 6. FILE UPLOAD HANDLER (ONLY FOR ADMIN) =================
@bot.message_handler(content_types=['document', 'video', 'audio', 'photo'])
def handle_files(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Sirf Bot Admin hi files upload kar sakte hain!")
        return

    if message.document: file_id, f_type, f_name = message.document.file_id, "document", message.document.file_name
    elif message.video: file_id, f_type, f_name = message.video.file_id, "video", "Video File"
    elif message.audio: file_id, f_type, f_name = message.audio.file_id, "audio", "Audio File"
    elif message.photo: file_id, f_type, f_name = message.photo[-1].file_id, "photo", "Photo"

    unique_key = str(uuid.uuid4())[:8]
    file_data = {
        "file_key": unique_key,
        "file_id": file_id,
        "type": f_type,
        "caption": message.caption or f"📁 {f_name}",
        "created_at": int(time.time())
    }
    
    # 1. Memory mein turant save karega
    MEM_FILES[unique_key] = file_data
    
    # 2. MongoDB mein permanent save karega
    db_status = "MongoDB Saved ✅"
    if files_col is not None:
        try:
            files_col.insert_one(file_data)
        except Exception as e:
            db_status = "Memory Saved ⚠️ (MongoDB Atlas mein 0.0.0.0/0 allow karein)"
            print(f"MongoDB File Save Error: {e}")

    bot_username = bot.get_me().username
    shareable_bot_link = f"https://t.me/{bot_username}?start=get_{unique_key}"

    reply_text = (
        f"✅ *File Linked with GPLinks!* ({db_status})\n\n"
        f"📄 *File Name:* `{f_name}`\n\n"
        f"🔗 *Aapka Channel Link (Ise share karein):*\n"
        f"`{shareable_bot_link}`"
    )
    bot.reply_to(message, reply_text, parse_mode="Markdown")

# ================= 7. DIRECT LINK SHORTENER (ONLY FOR ADMIN) =================
@bot.message_handler(func=lambda msg: msg.text and ("http://" in msg.text or "https://" in msg.text))
def handle_links(message):
    if message.from_user.id != ADMIN_ID:
        return

    wait = bot.reply_to(message, "🔗 *GPLinks se link short kiya ja raha hai...*", parse_mode="Markdown")
    short_link = shorten_url_gplinks(message.text.strip())
    bot.edit_message_text(f"✅ *Aapka GPLinks Short Link Taiyar Hai:*\n\n`{short_link}`", message.chat.id, wait.message_id, parse_mode="Markdown")

print("🚀 GPLinks + MongoDB + Broadcast Bot Starting...")
bot.remove_webhook()
time.sleep(1)
bot.infinity_polling(timeout=10, long_polling_timeout=5)
