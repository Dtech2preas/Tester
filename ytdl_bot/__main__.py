import os
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from .downloader import (
    download_media, get_video_info, format_duration, 
    format_file_size, SUPPORTED_SITES, download_as_gif
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "7661043379:AAHmQpb3bxXCmm9MlUaLDLXelpK6R4-wnDU"
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📹 Download Video", callback_data="help_video")],
        [InlineKeyboardButton("🎵 Download Audio", callback_data="help_audio")],
        [InlineKeyboardButton("🌐 Supported Sites", callback_data="help_sites")],
        [InlineKeyboardButton("❓ How to Use", callback_data="help_usage")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎬 *YouTube Downloader Bot*\n\n"
        "Simply send me a YouTube/Facebook/Instagram link and I'll download the video!\n\n"
        "Or use commands:\n"
        "`/audio <URL>` - Download as MP3\n"
        "`/gif <URL>` - Convert to GIF (max 10 seconds)\n"
        "`/info <URL>` - Get video details\n"
        "`/sites` - See all supported platforms\n\n"
        "⚠️ Max file size: 50MB (Telegram limit)",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_sites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sites_list = "\n".join([f"• {site}" for site in SUPPORTED_SITES])
    await update.message.reply_text(
        f"🌐 *Supported Sites*\n\n{sites_list}\n\n"
        f"Total: {len(SUPPORTED_SITES)} platforms\n\n"
        "Plus many more! yt-dlp supports 1000+ sites.",
        parse_mode='Markdown'
    )

async def video_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                caption=f"🎞️ {info.get('title', 'GIF')[:100]}\nConverted to GIF"
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
                    caption=f"🎥 {info.get('title', 'Video')[:200]}",
                    supports_streaming=True
                )
            else:
                await update.message.reply_audio(
                    audio=f, 
                    title=info.get('title', 'Audio')[:100],
                    performer=info.get('uploader', 'Unknown')[:50]
                )
        await status.delete()
        os.remove(filepath)
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status.edit_text(f"❌ Failed to download.\nError: {str(e)[:200]}")

async def download_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_download(update, context, 'video')

async def audio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_download(update, context, 'audio')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-download from URL without command"""
    text = update.message.text.strip()
    
    # Check if it's a URL (simple regex)
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    
    if urls:
        url = urls[0]  # Use first URL found
        context.args = [url]
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
            "I support YouTube, Facebook, Instagram, TikTok, and more!",
            parse_mode='Markdown'
        )
    elif data == "help_audio":
        await query.edit_message_text(
            "🎵 *Download Audio*\n\n"
            "Use: `/audio <URL>`\n\n"
            "Extracts audio as MP3 (if FFmpeg available) or original format.",
            parse_mode='Markdown'
        )
    elif data == "help_sites":
        sites_list = "\n".join([f"• {site}" for site in SUPPORTED_SITES[:20]])
        await query.edit_message_text(
            f"🌐 *Supported Sites*\n\n{sites_list}\n\n...and 1000+ more!",
            parse_mode='Markdown'
        )
    elif data == "help_usage":
        await query.edit_message_text(
            "❓ *How to Use*\n\n"
            "1️⃣ Send any video link - auto downloads!\n"
            "2️⃣ Use `/audio <URL>` for MP3\n"
            "3️⃣ Use `/gif <URL>` for GIF\n"
            "4️⃣ Use `/info <URL>` to preview\n\n"
            "⚠️ Videos over 50MB can't be sent due to Telegram limits.",
            parse_mode='Markdown'
        )

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
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