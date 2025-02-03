import os
import requests
import asyncio
import random
import sys
import motor.motor_asyncio
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
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
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = mongo_client["telegram_bot"]
users_collection = db["users"]

# Save user data to MongoDB
async def save_user(user_id):
    if not await users_collection.find_one({"user_id": user_id}):
        await users_collection.insert_one({"user_id": user_id})

# Get total users count
async def get_total_users():
    return await users_collection.count_documents({})

# Start Command
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    mention = update.effective_user.mention_html()

    # Save user to database
    await save_user(user_id)
    await context.bot.send_message(LOG_CHANNEL_ID, f"🆕 New User: {mention} (`{user_id}`)", parse_mode="HTML")

    start_text = (
        "✨ <b>Welcome to the Image Uploader Bot!</b>\n\n"
        "📌 <b>Features:</b>\n"
        "✅ Upload images & get a permanent link\n"
        "✅ Telegram emoji reactions 🎭\n"
        "✅ Fully automated & responsive\n"
        "✅ No storage limits – Upload as much as you want!\n\n"
        "🚀 <b>Just send an image to get started!</b>"
    )
    keyboard = [[InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/Soutick_09")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(start_text, reply_markup=reply_markup, parse_mode="HTML")

# Ban User
async def ban(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /ban <user_id>")

    user_id = int(context.args[0])
    await users_collection.delete_one({"user_id": user_id})
    await update.message.reply_text(f"🚫 User `{user_id}` has been banned.", parse_mode="HTML")

# Unban User
async def unban(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /unban <user_id>")

    user_id = int(context.args[0])
    await save_user(user_id)
    await update.message.reply_text(f"✅ User `{user_id}` has been unbanned.", parse_mode="HTML")

# Restart Bot
async def restart(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    await update.message.reply_text("🔄 Restarting bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# Stats Command
async def stats(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    total_users = await get_total_users()
    await update.message.reply_text(f"📊 <b>Total Users:</b> {total_users}", parse_mode="HTML")

# Handle Media Upload
async def handle_media(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    mention = update.effective_user.mention_html()

    file = update.message.photo[-1] if update.message.photo else update.message.document
    file_path = await context.bot.get_file(file.file_id)

    # Upload Progress Message
    status_message = await update.message.reply_text("📤 Uploading...")

    # Upload to ImgBB
    with requests.get(file_path.file_path, stream=True) as response:
        response.raise_for_status()
        files = {"image": response.content}
        res = requests.post(f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}", files=files)

    if res.status_code == 200:
        image_url = res.json()["data"]["image"]["url"]
        await update.message.reply_text(image_url)
    else:
        await update.message.reply_text("❌ Upload failed! Please try again.")

    # Delete Uploading Message
    await context.bot.delete_message(chat_id=status_message.chat_id, message_id=status_message.message_id)

    # Forward Image to Log Channel
    caption_text = f"📸 <b>Image received from:</b> {mention} (`{user_id}`)"
    await context.bot.send_photo(chat_id=LOG_CHANNEL_ID, photo=file.file_id, caption=caption_text, parse_mode="HTML")

    # React with Emoji
    await update.message.reply_reaction("🔥")

# Broadcast Command
async def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to a message to broadcast it!")

    total_users = await get_total_users()
    sent_count = 0
    status_message = await update.message.reply_text(f"📢 Broadcasting... 0/{total_users}")

    async for user in users_collection.find():
        user_id = user["user_id"]
        try:
            await context.bot.forward_message(chat_id=user_id, from_chat_id=update.message.chat_id, message_id=update.message.reply_to_message.message_id)
            sent_count += 1
        except Exception:
            pass  # Ignore errors (e.g., user blocked bot)

        if sent_count % 2 == 0:
            await status_message.edit_text(f"📢 Broadcasting... {sent_count}/{total_users}")
            await asyncio.sleep(1)

    await status_message.edit_text(f"✅ Broadcast Completed! Sent to {sent_count}/{total_users} users.")

# Main Function
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))

    # Media Handler
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media))

    # Start Bot
    application.run_polling()

if __name__ == "__main__":
    main()
