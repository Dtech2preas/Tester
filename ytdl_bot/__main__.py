import os
import logging
import re
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from .downloader import (
    download_media, get_video_info, format_duration, 
    format_file_size, SUPPORTED_SITES, download_as_gif
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "7661043379:AAHmQpb3bxXCmm9MlUaLDLXelpK6R4-wnDU"
ADMIN_USERNAME = "PREASX24"
REQUIRED_CHANNEL = "@DTECHX24"
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(list(users), f)

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, 'w') as f:
            json.dump(list(users), f)
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set.")

# Store progress messages for updating
user_progress = {}

def progress_hook(chat_id, message_id):
    """Create a progress hook for a specific chat"""
    def hook(d):
        if d['status'] == 'downloading':
            try:
                percent = d.get('_percent_str', '0%').strip()
                speed = d.get('_speed_str', '0 B/s').strip()
                eta = d.get('_eta_str', '?').strip()
                downloaded = d.get('_downloaded_str', '0 B').strip()
                total = d.get('_total_str', '?').strip()
                
                progress_text = f"⬇️ Downloading...\n{percent}\n📦 {downloaded} / {total}\n⚡ {speed}\n⏱️ ETA: {eta}"
                
                # Update progress message (simplified - would need async)
                logger.info(f"Progress: {percent} - {speed}")
            except:
                pass
        elif d['status'] == 'finished':
            logger.info("Download finished, processing...")
    return hook

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    users = load_users()
    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: {len(users)}\n"
        f"🤖 Bot Status: Online",
        parse_mode='Markdown'
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Please provide a message to broadcast.\nExample: `/broadcast Hello everyone!`", parse_mode='Markdown')
        return

    message = " ".join(context.args)
    users = load_users()

    status_msg = await update.message.reply_text(f"🚀 Broadcasting message to {len(users)} users...")

    success_count = 0
    fail_count = 0

    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 *Announcement*\n\n{message}", parse_mode='Markdown')
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            fail_count += 1

    await status_msg.edit_text(
        f"✅ *Broadcast Complete*\n\n"
        f"✉️ Successfully sent: {success_count}\n"
        f"❌ Failed: {fail_count}\n"
        f"👥 Total reached: {len(users)}",
        parse_mode='Markdown'
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)

    if not await check_subscription(update, context):
        return

    keyboard = [
        [InlineKeyboardButton("📹 Download Video", callback_data="help_video")],
        [InlineKeyboardButton("🎵 Download Audio", callback_data="help_audio")],
        [InlineKeyboardButton("🌐 Supported Sites", callback_data="help_sites")],
        [InlineKeyboardButton("❓ How to Use", callback_data="help_usage")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚡ *DTECH DOWNLOADER* ⚡\n\n"
        "Simply send me a YouTube/Facebook/Instagram link and I'll download the video!\n\n"
        "Or use commands:\n"
        "`/audio <URL>` - Download as MP3\n"
        "`/gif <URL>` - Convert to GIF (max 10 seconds)\n"
        "`/info <URL>` - Get video details\n"
        "`/sites` - See all supported platforms\n\n"
        "⚠️ Max file size: 50MB (Telegram limit)\n"
        f"👨‍💻 Need help? Contact: @{ADMIN_USERNAME}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sites_list = "\n".join([f"• {site}" for site in SUPPORTED_SITES])
    await update.message.reply_text(
        f"🌐 *Supported Sites*\n\n{sites_list}\n\n"
        f"Total: {len(SUPPORTED_SITES)} platforms\n\n"
        "Plus many more! yt-dlp supports 1000+ sites.\n"
        f"👨‍💻 Contact: @{ADMIN_USERNAME}",
        parse_mode='Markdown'
    )

async def video_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    if not await check_subscription(update, context):
        return

    if not context.args:
        await update.message.reply_text("Please provide a URL.\nExample: `/info https://youtu.be/...`", parse_mode='Markdown')
        return
    
    url = context.args[0]
    status = await update.message.reply_text("🔍 Fetching video information...")
    
    try:
        info = get_video_info(url)
        if info:
            duration = format_duration(info['duration'])
            size = format_file_size(info['filesize'])
            
            info_text = (
                f"📹 *{info['title']}*\n\n"
                f"👤 Channel: {info['uploader']}\n"
                f"⏱️ Duration: {duration}\n"
                f"👁️ Views: {info['views']:,}\n"
                f"💾 Size: {size}\n"
                f"🎬 Formats available: {info['formats']}\n\n"
                f"🔗 [Open in Browser]({info['webpage_url']})"
            )
            await status.edit_text(info_text, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            await status.edit_text("❌ Could not fetch video information. Make sure the URL is valid.")
    except Exception as e:
        await status.edit_text(f"❌ Error: {str(e)[:200]}")

async def download_as_gif_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user.id)
    if not await check_subscription(update, context):
        return

    if not context.args:
        await update.message.reply_text(
            "Please provide a URL.\n\n"
            "Examples:\n"
            "`/gif https://youtu.be/...` (full video)\n"
            "`/gif https://youtu.be/... 10` (first 10 seconds)\n"
            "`/gif https://youtu.be/... 5:30-5:45` (specific segment)",
            parse_mode='Markdown'
        )
        return
    
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Could not delete message: {e}")

    url = context.args[0]
    start_time = None
    end_time = None
    
    # Parse time arguments
    if len(context.args) > 1:
        time_arg = context.args[1]
        if '-' in time_arg:
            times = time_arg.split('-')
            start_time = parse_time(times[0])
            if len(times) > 1:
                end_time = parse_time(times[1])
        else:
            # Assume it's just a duration from start
            end_time = parse_time(time_arg)
            start_time = 0
    
    status = await update.message.reply_text("🎬 Converting to GIF... This may take a moment.")
    
    try:
        filepath, info = download_as_gif(url, start_time, end_time)
        
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        if file_size > 50:
            await status.edit_text(f"❌ GIF too large ({file_size:.1f}MB > 50MB)")
            os.remove(filepath)
            return
        
        with open(filepath, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(filepath),
                caption=f"⚡ *DTECH DOWNLOADER* ⚡\n\n🎞️ {info.get('title', 'GIF')[:100]}\n👨‍💻 @{ADMIN_USERNAME}",
                parse_mode='Markdown'
            )
        await status.delete()
        os.remove(filepath)
    except Exception as e:
        await status.edit_text(f"❌ Failed to create GIF: {str(e)[:200]}")

def parse_time(time_str):
    """Parse time string like '5:30' or '90' to seconds"""
    time_str = str(time_str).strip()
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    try:
        return int(time_str)
    except:
        return 0

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE, mode='video', quality='best'):
    save_user(update.effective_user.id)
    if not await check_subscription(update, context):
        return

    if not context.args:
        await update.message.reply_text("Please provide a URL.\nExample: `/download https://youtu.be/...`", parse_mode='Markdown')
        return
    
    url = context.args[0]
    status = await update.message.reply_text(f"⏳ Downloading {mode}... This may take a while.")
    
    try:
        # Create progress callback
        def progress(d):
            if d['status'] == 'downloading':
                try:
                    percent = d.get('_percent_str', '0%').strip()
                    speed = d.get('_speed_str', '0 B/s').strip()
                    # Note: Updating message in sync hook is tricky; we log instead
                    logger.info(f"Download progress: {percent} at {speed}")
                except:
                    pass
        
        filepath, info = download_media(url, mode, quality, progress)
        
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        if file_size > 50:
            await status.edit_text(f"❌ File too large ({file_size:.1f}MB > 50MB Telegram limit)\nTry a lower quality or different video.")
            os.remove(filepath)
            return
        
        with open(filepath, 'rb') as f:
            if mode == 'video':
                await update.message.reply_video(
                    video=f, 
                    caption=f"⚡ *DTECH DOWNLOADER* ⚡\n\n🎥 {info.get('title', 'Video')[:100]}\n👨‍💻 @{ADMIN_USERNAME}",
                    supports_streaming=True,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_audio(
                    audio=f, 
                    title=info.get('title', 'Audio')[:100],
                    performer=info.get('uploader', 'Unknown')[:50],
                    caption=f"⚡ *DTECH DOWNLOADER* ⚡\n👨‍💻 @{ADMIN_USERNAME}",
                    parse_mode='Markdown'
                )
        await status.delete()
        os.remove(filepath)
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status.edit_text(f"❌ Failed to download.\nError: {str(e)[:200]}")

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Could not delete message: {e}")
    await handle_download(update, context, 'video')

async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Could not delete message: {e}")
    await handle_download(update, context, 'audio')

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ['left', 'kicked']:
            keyboard = [[InlineKeyboardButton("Join Channel 🛡️", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🤖 *DTECH DOWNLOADER*\n\n"
                "To use this bot, you must join our official channel first.\n\n"
                f"Please join {REQUIRED_CHANNEL} and try again! ⚡",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        # If there's an error (e.g. bot not in channel), let them use it to avoid breaking
        return True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-download from URL without command"""
    save_user(update.effective_user.id)

    if not await check_subscription(update, context):
        return

    text = update.message.text.strip()
    
    # Check if it's a URL (simple regex)
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    
    if urls:
        url = urls[0]  # Use first URL found
        context.args = [url]
        # Auto-delete user's message containing the link
        try:
            await update.message.delete()
        except Exception as e:
            logger.error(f"Could not delete message: {e}")
        await handle_download(update, context, 'video')
    else:
        await update.message.reply_text(
            "Send me a YouTube/Facebook/Instagram link and I'll download it!\n\n"
            "Commands:\n"
            "/audio <URL> - Download as MP3\n"
            "/gif <URL> - Convert to GIF\n"
            "/info <URL> - Get video details\n"
            "/sites - See supported platforms"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "help_video":
        await query.edit_message_text(
            "📹 *Download Video*\n\n"
            "Just send me any video link or use:\n"
            "`/download <URL>`\n\n"
            "I support YouTube, Facebook, Instagram, TikTok, and more!\n\n"
            f"👨‍💻 Contact: @{ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
    elif data == "help_audio":
        await query.edit_message_text(
            "🎵 *Download Audio*\n\n"
            "Use: `/audio <URL>`\n\n"
            "Extracts audio as MP3 (if FFmpeg available) or original format.\n\n"
            f"👨‍💻 Contact: @{ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
    elif data == "help_sites":
        sites_list = "\n".join([f"• {site}" for site in SUPPORTED_SITES[:20]])
        await query.edit_message_text(
            f"🌐 *Supported Sites*\n\n{sites_list}\n\n...and 1000+ more!\n\n"
            f"👨‍💻 Contact: @{ADMIN_USERNAME}",
            parse_mode='Markdown'
        )
    elif data == "help_usage":
        await query.edit_message_text(
            "❓ *How to Use*\n\n"
            "1️⃣ Send any video link - auto downloads!\n"
            "2️⃣ Use `/audio <URL>` for MP3\n"
            "3️⃣ Use `/gif <URL>` for GIF\n"
            "4️⃣ Use `/info <URL>` to preview\n\n"
            "⚠️ Videos over 50MB can't be sent due to Telegram limits.\n\n"
            f"👨‍💻 Contact: @{ADMIN_USERNAME}",
            parse_mode='Markdown'
        )

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("sites", show_sites))
    app.add_handler(CommandHandler("info", video_info))
    app.add_handler(CommandHandler("download", download_command))
    app.add_handler(CommandHandler("audio", audio_command))
    app.add_handler(CommandHandler("gif", download_as_gif_command))
    
    # Auto-download URLs
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback handler for inline keyboards
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("Bot started with all features enabled!")
    app.run_polling()

if __name__ == "__main__":
    main()