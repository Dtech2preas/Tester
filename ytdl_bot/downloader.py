import os
import re
import yt_dlp
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Supported sites list
SUPPORTED_SITES = [
    "YouTube", "Facebook", "Instagram", "TikTok", "Twitter/X", "Reddit",
    "Twitch", "Vimeo", "Dailymotion", "Bilibili", "SoundCloud", "Spotify",
    "Rumble", "Odysee", "LinkedIn", "Telegram", "Tumblr", "Pinterest"
]

def sanitize_filename(title, max_length=150):
    """Remove invalid characters and truncate long filenames"""
    title = re.sub(r'[<>:"/\\|?*]', '', title)
    title = re.sub(r'[\x00-\x1f\x7f]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    if len(title) > max_length:
        title = title[:max_length].rsplit(' ', 1)[0]
    if not title:
        title = "video"
    return title

def get_video_info(url):
    """Extract video information without downloading"""
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'views': info.get('view_count', 0),
                'filesize': info.get('filesize', 0) or info.get('filesize_approx', 0),
                'thumbnail': info.get('thumbnail', ''),
                'formats': len(info.get('formats', [])),
                'webpage_url': info.get('webpage_url', url)
            }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None

def format_duration(seconds):
    """Convert seconds to readable format"""
    if not seconds:
        return "Unknown"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def format_file_size(bytes_size):
    """Convert bytes to readable format"""
    if not bytes_size:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} GB"

def download_media(url, mode='video', quality='best', progress_callback=None):
    """
    Download video or audio with progress tracking
    Returns file path and video info
    """
    os.makedirs("downloads", exist_ok=True)
    
    # First get info for sanitized filename
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as temp_ydl:
        info = temp_ydl.extract_info(url, download=False)
        original_title = info.get('title', 'video')
        safe_title = sanitize_filename(original_title)
    
    # Configure format based on quality and mode
    if mode == 'video':
        quality_map = {
            'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]',
            '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]',
            '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]',
        }
        format_spec = quality_map.get(quality, quality_map['best'])
    else:  # audio
        format_spec = 'bestaudio/best'
    
    opts = {
        'format': format_spec,
        'outtmpl': f'downloads/{safe_title}.%(ext)s',
        'quiet': False,
        'no_warnings': True,
        'restrictfilenames': True,
        'progress_hooks': [progress_callback] if progress_callback else [],
    }
    
    # Audio post-processing (convert to MP3 if FFmpeg available)
    if mode == 'audio':
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        opts['outtmpl'] = f'downloads/{safe_title}.%(ext)s'
    
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
        
        # Find downloaded file
        for f in os.listdir('downloads'):
            if f.startswith(safe_title) or safe_title in f:
                filepath = os.path.join('downloads', f)
                return filepath, info
    
    raise FileNotFoundError(f"Could not find downloaded file for {safe_title}")

def download_as_gif(url, start_time=None, end_time=None, progress_callback=None):
    """
    Download video and convert to GIF (requires FFmpeg)
    """
    os.makedirs("downloads", exist_ok=True)
    
    # Get video info first
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as temp_ydl:
        info = temp_ydl.extract_info(url, download=False)
        original_title = info.get('title', 'gif')
        safe_title = sanitize_filename(original_title, max_length=100)
    
    # Create segment filter if time range provided
    if start_time or end_time:
        time_filter = []
        if start_time:
            time_filter.append(f"start={start_time}")
        if end_time:
            time_filter.append(f"end={end_time}")
        download_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads/temp_{safe_title}.%(ext)s',
            'quiet': True,
            'download_ranges': [{
                'start_time': start_time or 0,
                'end_time': end_time or None
            }],
            'force_keyframes': True,
        }
    else:
        download_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads/temp_{safe_title}.%(ext)s',
            'quiet': True,
        }
    
    # Download the video
    with yt_dlp.YoutubeDL(download_opts) as ydl:
        ydl.extract_info(url, download=True)
    
    # Find downloaded video
    video_file = None
    for f in os.listdir('downloads'):
        if f.startswith(f'temp_{safe_title}'):
            video_file = os.path.join('downloads', f)
            break
    
    if not video_file:
        raise FileNotFoundError("Could not find downloaded video")
    
    # Convert to GIF (requires FFmpeg)
    gif_filename = f'downloads/{safe_title}.gif'
    
    # Try to use FFmpeg for GIF conversion
    import subprocess
    try:
        cmd = ['ffmpeg', '-i', video_file, '-vf', 'fps=10,scale=320:-1:flags=lanczos', '-loop', '0', gif_filename]
        subprocess.run(cmd, capture_output=True, check=True)
        
        # Clean up temp video
        os.remove(video_file)
        
        if os.path.exists(gif_filename):
            return gif_filename, info
        else:
            raise Exception("GIF conversion failed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # FFmpeg not available, return error
        os.remove(video_file)
        raise Exception("FFmpeg not available on server. GIF conversion requires FFmpeg.")