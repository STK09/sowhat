import os
import requests
import asyncio
import random
import sys
import datetime
import pytz
from pymongo import MongoClient
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

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
users_collection = db["users"]

# Timezone setup
IST = pytz.timezone("Asia/Kolkata")

# Start Command
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    # Build the mention using the correct URL scheme.
    mention = f'<a href="tg://openmessage?user_id={user_id}">{user.full_name}</a>'

    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id})
        await context.bot.send_message(
            LOG_CHANNEL_ID,
            f"🆕 New User: {mention} (`{user_id}`)",
            parse_mode="HTML"
        )

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
    users_collection.delete_one({"user_id": user_id})
    await update.message.reply_text(f"🚫 User `{user_id}` has been banned.", parse_mode="HTML")
    try:
        await context.bot.send_message(
            user_id,
            "❌ You have been banned from using this bot. Contact @Soutick_09 to get unbanned!"
        )
    except Exception:
        pass

# Unban a user
async def unban(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /unban <user_id>")

    user_id = int(context.args[0])
    users_collection.insert_one({"user_id": user_id})
    await update.message.reply_text(f"✅ User `{user_id}` has been unbanned.", parse_mode="HTML")
    try:
        await context.bot.send_message(
            user_id,
            "✅ You have been unbanned! You can use the bot again."
        )
    except Exception:
        pass

# Restart bot
async def restart(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    await update.message.reply_text("🔄 Restarting bot...")
    now = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    await context.bot.send_message(
        LOG_CHANNEL_ID,
        f"♻️ Bot restarted successfully.\n🕒 Restarted on: <b>{now} IST</b>",
        parse_mode="HTML"
    )
    os.execl(sys.executable, sys.executable, *sys.argv)

# Stats command
async def stats(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")

    total_users = users_collection.count_documents({})
    await update.message.reply_text(f"📊 <b>Total Users:</b> {total_users}", parse_mode="HTML")

# Handle media upload
async def handle_media(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    mention = f'<a href="tg://openmessage?user_id={user_id}">{user.full_name}</a>'

    file = update.message.photo[-1] if update.message.photo else update.message.document
    file_path = await context.bot.get_file(file.file_id)

    status_message = await update.message.reply_text("📤 Uploading...")

    # Download image data from the Telegram file URL.
    response = requests.get(file_path.file_path, stream=True)
    response.raise_for_status()
    files = {"image": response.content}
    res = requests.post(f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}", files=files)

    if res.status_code == 200:
        image_url = res.json()["data"]["image"]["url"]
        keyboard = [[InlineKeyboardButton("📋 Copy Link", url=image_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ <b>Upload Successful!</b>", reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Upload failed! Please try again.")

    await context.bot.delete_message(chat_id=status_message.chat_id, message_id=status_message.message_id)

    caption_text = f"📸 <b>Image received from:</b> {mention} (`{user_id}`)"
    await context.bot.send_photo(
        chat_id=LOG_CHANNEL_ID,
        photo=file.file_id,
        caption=caption_text,
        parse_mode="HTML"
    )

    # Since Telegram bots cannot add built-in reactions to user messages,
    # we simulate a reaction by replying with an emoji and deleting that reply shortly after.
    reactions = ["🔥", "😎", "👍", "😍", "🤩", "👏", "💯", "😂", "😜", "💖"]
    reaction = random.choice(reactions)
    try:
        reaction_msg = await update.message.reply_text(reaction, quote=False)
        await asyncio.sleep(2)
        await reaction_msg.delete()
    except Exception:
        pass

# Broadcast command with inline buttons/links support and concurrency improvements
async def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("⚠️ Only the bot owner can use this command.")
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("Reply to a message to broadcast!")
    
    msg = update.message.reply_to_message
    total_users = users_collection.count_documents({})
    sent_count = 0
    status_message = await update.message.reply_text(f"📢 Broadcasting... 0/{total_users}")
    
    semaphore = asyncio.Semaphore(10)  # Limit concurrent sends to 10

    async def send_to_user(user_id):
        nonlocal sent_count
        async with semaphore:
            try:
                if msg.text:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=msg.text,
                        parse_mode=msg.parse_mode,
                        reply_markup=msg.reply_markup,
                        disable_web_page_preview=msg.disable_web_page_preview
                    )
                elif msg.photo:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=msg.photo[-1].file_id,
                        caption=msg.caption,
                        parse_mode=msg.parse_mode,
                        reply_markup=msg.reply_markup
                    )
                elif msg.document:
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=msg.document.file_id,
                        caption=msg.caption,
                        parse_mode=msg.parse_mode,
                        reply_markup=msg.reply_markup
                    )
                else:
                    # Fallback: use copy if the message type isn’t directly handled
                    await msg.copy(chat_id=user_id)
                sent_count += 1
            except Exception:
                pass

    tasks = []
    for user in users_collection.find():
        user_id = user["user_id"]
        tasks.append(asyncio.create_task(send_to_user(user_id)))
    
    async def update_status():
        while any(not t.done() for t in tasks):
            try:
                await status_message.edit_text(f"📢 Broadcasting... {sent_count}/{total_users}")
            except Exception:
                pass
            await asyncio.sleep(1)
    
    status_task = asyncio.create_task(update_status())
    await asyncio.gather(*tasks)
    status_task.cancel()
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

    application.run_polling()

if __name__ == "__main__":
    main()
