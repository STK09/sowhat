import os
import requests
import asyncio
import random
import json
import sys
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# User data file
USER_DATA_FILE = "users.json"
registered_users = set()

# Load user data
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "r") as f:
        registered_users = set(json.load(f))

# Save user data
def save_users():
    with open(USER_DATA_FILE, "w") as f:
        json.dump(list(registered_users), f)

# Start Command
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    mention = update.effective_user.mention_html()

    if user_id not in registered_users:
        registered_users.add(user_id)
        save_users()
        await context.bot.send_message(LOG_CHANNEL_ID, f"🆕 New User: {mention} (`{user_id}`)")

    start_text = (
        "✨ **Welcome to the Image Uploader Bot!**\n\n"
        "📌 **Features:**\n"
        "✅ Upload images & get a permanent link\n"
        "✅ Fully automated & responsive\n"
        "✅ No storage limits – Upload as much as you want!\n\n"
        "🚀 **Just send an image to get started!**"
    )
    keyboard = [[InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/Soutick_09")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(start_text, reply_markup=reply_markup)

# Ban a user
async def ban(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /ban <user_id>")

    user_id = int(context.args[0])
    registered_users.discard(user_id)
    save_users()
    await update.message.reply_text(f"🚫 User `{user_id}` has been banned.")

# Unban a user
async def unban(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /unban <user_id>")

    user_id = int(context.args[0])
    registered_users.add(user_id)
    save_users()
    await update.message.reply_text(f"✅ User `{user_id}` has been unbanned.")

# Restart bot
async def restart(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    await update.message.reply_text("🔄 Restarting bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)

# Stats command
async def stats(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    total_users = len(registered_users)
    await update.message.reply_text(f"📊 Total Users: {total_users}")

# Handle media upload
async def handle_media(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    mention = update.effective_user.mention_markdown_v2()

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
    caption_text = f"📸 Image received from [{update.effective_user.first_name}](tg://user?id={user_id}) (`{user_id}`)"
    await context.bot.send_photo(chat_id=LOG_CHANNEL_ID, photo=file.file_id, caption=caption_text, parse_mode="Markdown")

    # Send Random Reaction
    reactions = ["🔥", "😎", "👍", "😍", "🤩", "👏", "💯", "😂"]
    await update.message.reply_text(random.choice(reactions))

# Broadcast command
async def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <message>")
    
    message_text = " ".join(context.args)
    total_users = len(registered_users)
    sent_count = 0

    status_message = await update.message.reply_text(f"📢 Broadcasting... 0/{total_users}")

    for index, user_id in enumerate(registered_users, start=1):
        try:
            await context.bot.send_message(user_id, text=message_text, parse_mode="Markdown")
            sent_count += 1
        except Exception:
            pass  # Ignore errors (e.g., user blocked bot)
        
        if index % 2 == 0:  # Update status every 2 messages
            await status_message.edit_text(f"📢 Broadcasting... {sent_count}/{total_users}")
            await asyncio.sleep(1)

    await status_message.edit_text(f"✅ Broadcast Completed! Sent to {sent_count}/{total_users} users.")

# Main function
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))

    # Media handler
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media))

    # Start bot
    application.run_polling()

if __name__ == "__main__":
    main()
