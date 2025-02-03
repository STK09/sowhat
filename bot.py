import os
import requests
import asyncio
import random
import json
import sys
import pymongo
from datetime import datetime
import pytz
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackContext
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["TelegramBot"]
users_collection = db["users"]

# Get registered users from MongoDB
def get_registered_users():
    return set(user["user_id"] for user in users_collection.find({}, {"_id": 0, "user_id": 1}))

# Register a user
def register_user(user_id):
    if users_collection.find_one({"user_id": user_id}) is None:
        users_collection.insert_one({"user_id": user_id})

# Remove a user (ban)
def remove_user(user_id):
    users_collection.delete_one({"user_id": user_id})

# Start Command
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    mention = update.effective_user.mention_html()

    if user_id not in get_registered_users():
        register_user(user_id)
        await context.bot.send_message(LOG_CHANNEL_ID, f"🆕 New User: {mention} (`{user_id}`)")

    start_text = (
        "✨ <b>Welcome to the Image Uploader Bot!</b>\n\n"
        "📌 <b>Features:</b>\n"
        "✅ Upload images & get a permanent link\n"
        "✅ Fully automated & responsive\n"
        "✅ No storage limits – Upload as much as you want!\n\n"
        "🚀 <b>Just send an image to get started!</b>"
    )
    keyboard = [[InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/Soutick_09")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(start_text, reply_markup=reply_markup, parse_mode="HTML")

# Ban a user
async def ban(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /ban <user_id>")

    user_id = int(context.args[0])
    remove_user(user_id)
    await update.message.reply_text(f"🚫 User `{user_id}` has been banned.", parse_mode="Markdown")
    
    try:
        await context.bot.send_message(user_id, "🚫 You have been banned from using this bot. Contact @Soutick_09 to get unbanned!")
    except:
        pass

# Unban a user
async def unban(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /unban <user_id>")

    user_id = int(context.args[0])
    register_user(user_id)
    await update.message.reply_text(f"✅ User `{user_id}` has been unbanned.", parse_mode="Markdown")
    
    try:
        await context.bot.send_message(user_id, "✅ You have been unbanned by @Soutick_09! You can now use the bot again.")
    except:
        pass

# Restart bot
async def restart(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    await update.message.reply_text("🔄 Restarting bot...")
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist).strftime("%Y-%m-%d %I:%M %p IST")
    await context.bot.send_message(LOG_CHANNEL_ID, f"🔄 Bot restarted successfully on {now}")
    
    os.execl(sys.executable, sys.executable, *sys.argv)

# Stats command
async def stats(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    total_users = users_collection.count_documents({})
    await update.message.reply_text(f"📊 <b>Total Users:</b> {total_users}", parse_mode="HTML")

# Handle media upload
async def handle_media(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    file = update.message.photo[-1] if update.message.photo else update.message.document
    file_path = await context.bot.get_file(file.file_id)

    status_message = await update.message.reply_text("📤 Uploading...")

    with requests.get(file_path.file_path, stream=True) as response:
        response.raise_for_status()
        files = {"image": response.content}
        res = requests.post(f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}", files=files)

    if res.status_code == 200:
        image_url = res.json()["data"]["image"]["url"]
        await update.message.reply_text(image_url)
    else:
        await update.message.reply_text("❌ Upload failed! Please try again.")

    await context.bot.delete_message(chat_id=status_message.chat_id, message_id=status_message.message_id)
    
    # Telegram Reaction
    reactions = ["👍", "🔥", "😂", "😍", "👏", "💯", "🤩", "😎"]
    await update.message.react(ReactionTypeEmoji(random.choice(reactions)))

# Broadcast command (supports all media types)
async def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    message = update.message
    total_users = users_collection.count_documents({})
    sent_count = 0

    status_message = await update.message.reply_text(f"📢 Broadcasting... 0/{total_users}")

    for index, user in enumerate(users_collection.find({}, {"_id": 0, "user_id": 1})):
        try:
            await message.copy(chat_id=user["user_id"])
            sent_count += 1
        except:
            pass
        
        if index % 2 == 0:
            await status_message.edit_text(f"📢 Broadcasting... {sent_count}/{total_users}")
            await asyncio.sleep(1)

    await status_message.edit_text(f"✅ Broadcast Completed! Sent to {sent_count}/{total_users} users.")

# Main function
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media))

    application.run_polling()

if __name__ == "__main__":
    main()
