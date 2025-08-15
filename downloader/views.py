import os
import logging
from pathlib import Path
from rest_framework.response import Response
from rest_framework.decorators import api_view
import yt_dlp

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOWNLOAD_PATH = Path.home() / "Videos" / "IntechDownloader"
DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)

# Log the download path for debugging
logger.info(f"Download path set to: {DOWNLOAD_PATH}")
logger.info(f"Download path exists: {DOWNLOAD_PATH.exists()}")
logger.info(f"Download path is writable: {os.access(DOWNLOAD_PATH, os.W_OK)}")

@api_view(['POST'])
def download_video(request):
    url = request.data.get('url')
    resolution = request.data.get('resolution', '1080p')
    download_type = request.data.get('download_type', 'video') 
    fallback_resolution = request.data.get('fallback_resolution', '720p')
    platform = request.data.get('platform', 'auto')

    logger.info(f"Download request: URL={url}, resolution={resolution}, platform={platform}")

    if not url:
        return Response({"error": "URL is required"}, status=400)

    # Platform-specific format configurations
    platform_format_map = {
        'youtube': {
            "best": "bestvideo+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best",
            "720p": "bestvideo[height<=720]+bestaudio/best[ext=mp4]/best",
            "480p": "bestvideo[height<=480]+bestaudio/best[ext=mp4]/best",
            "360p": "bestvideo[height<=360]+bestaudio/best[ext=mp4]/best",
        },
        'tiktok': {
            "best": "best[ext=mp4]",
            "1080p": "best[height<=1080][ext=mp4]",
            "720p": "best[height<=720][ext=mp4]",
            "480p": "best[height<=480][ext=mp4]",
        },
        'twitter': {
            "best": "best[ext=mp4]",
            "1080p": "best[height<=1080][ext=mp4]",
            "720p": "best[height<=720][ext=mp4]",
        },
        'instagram': {
            "best": "best[ext=mp4]",
            "1080p": "best[height<=1080][ext=mp4]",
            "720p": "best[height<=720][ext=mp4]",
        }
    }

    # Auto-detect platform
    if platform == 'auto':
        platform_extractors = {
            'youtube': ['youtube.com', 'youtu.be'],
            'tiktok': ['tiktok.com'],
            'twitter': ['twitter.com', 'x.com'],
            'instagram': ['instagram.com']
        }
        for detected_platform, domains in platform_extractors.items():
            if any(domain in url for domain in domains):
                platform = detected_platform
                break
        else:
            platform = 'youtube'

    logger.info(f"Detected platform: {platform}")

    format_map = platform_format_map.get(platform, platform_format_map['youtube'])
    selected_format = format_map.get(resolution, format_map.get('1080p'))
    
    logger.info(f"Selected format: {selected_format}")

    # Create output template with more sanitization
    output_template = str(DOWNLOAD_PATH / f"{platform}_%(title).100s.%(ext)s")
    logger.info(f"Output template: {output_template}")

    ydl_opts = {
        'format': selected_format,
        'outtmpl': output_template,
        'noplaylist': download_type != 'playlist',
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'verbose': True,
        'ignoreerrors': False,  # Changed to False to catch errors
        'geo_bypass': True,
        'allow_multiple_audio_streams': True,
        'nooverwrites': False,  # Allow overwrites for debugging
        # Add progress hook for debugging
        'progress_hooks': [progress_hook],
    }

    # Platform-specific options
    if platform == 'tiktok':
        ydl_opts.update({
            'extractor_retries': 3,
            'no_color': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        })
    elif platform == 'twitter':
        ydl_opts['twitter_include_replies'] = False
    elif platform == 'instagram':
        ydl_opts['no_color'] = True

    def attempt_download(opts):
        """Helper function to attempt download with given options"""
        with yt_dlp.YoutubeDL(opts) as ydl:
            logger.info("Starting download...")
            info = ydl.extract_info(url, download=True)
            
            # Check if files were actually created
            files_created = list(DOWNLOAD_PATH.glob("*"))
            logger.info(f"Files in download directory after download: {len(files_created)}")
            for file in files_created[-5:]:  # Show last 5 files
                logger.info(f"  - {file.name} (size: {file.stat().st_size} bytes)")
            
            return info

    try:
        info = attempt_download(ydl_opts)
        
        if 'entries' in info:
            # Playlist handling
            successful_downloads = []
            failed_downloads = []
            
            for entry in info.get('entries', []):
                if entry:
                    successful_downloads.append({
                        'title': entry.get('title', 'Unknown'),
                        'resolution': entry.get('height', 'Unknown'),
                        'format': entry.get('format', 'Unknown'),
                        'filepath': entry.get('filepath', 'Unknown')
                    })
                else:
                    failed_downloads.append('Unknown (extraction failed)')
            
            return Response({
                "message": f"{platform.capitalize()} Playlist downloaded successfully ({len(successful_downloads)} videos)",
                "platform": platform,
                "download_path": str(DOWNLOAD_PATH),
                "successful": successful_downloads,
                "failed": failed_downloads,
                "files_in_directory": len(list(DOWNLOAD_PATH.glob("*")))
            })
        else:
            # Single video handling
            return Response({
                "message": f"{platform.capitalize()} Download successful", 
                "platform": platform,
                "title": info.get('title'), 
                "resolution": info.get('height'),
                "format": info.get('format'),
                "filepath": info.get('filepath', 'Unknown'),
                "download_path": str(DOWNLOAD_PATH),
                "files_in_directory": len(list(DOWNLOAD_PATH.glob("*")))
            })
            
    except Exception as e:
        logger.error(f"Primary download failed: {str(e)}")
        
        # Try fallback resolution
        if resolution != fallback_resolution and fallback_resolution in format_map:
            logger.info(f"Attempting fallback resolution: {fallback_resolution}")
            ydl_opts['format'] = format_map[fallback_resolution]
            
            try:
                info = attempt_download(ydl_opts)
                return Response({
                    "message": f"{platform.capitalize()} Download successful with fallback resolution ({fallback_resolution})",
                    "platform": platform,
                    "title": info.get('title') if 'entries' not in info else f"Playlist with {len(info.get('entries', []))} videos",
                    "download_path": str(DOWNLOAD_PATH),
                    "files_in_directory": len(list(DOWNLOAD_PATH.glob("*")))
                })
            except Exception as fallback_error:
                logger.error(f"Fallback download failed: {str(fallback_error)}")
                return Response({
                    "error": f"{platform.capitalize()} Download failed (both primary and fallback)",
                    "primary_error": str(e),
                    "fallback_error": str(fallback_error),
                    "download_path": str(DOWNLOAD_PATH)
                }, status=500)
        
        return Response({
            "error": f"{platform.capitalize()} Download failed",
            "details": str(e),
            "download_path": str(DOWNLOAD_PATH)
        }, status=500)

def progress_hook(d):
    """Progress hook for yt-dlp to track download progress"""
    if d['status'] == 'downloading':
        logger.info(f"Downloading: {d.get('_percent_str', 'N/A')} of {d.get('filename', 'Unknown file')}")
    elif d['status'] == 'finished':
        logger.info(f"Download finished: {d.get('filename', 'Unknown file')}")
        # Verify file exists and has content
        filepath = Path(d.get('filename', ''))
        if filepath.exists():
            logger.info(f"File verified: {filepath.name} ({filepath.stat().st_size} bytes)")
        else:
            logger.warning(f"File not found after download: {filepath}")

@api_view(['GET'])
def debug_info(request):
    """Debug endpoint to check system status"""
    files_in_dir = list(DOWNLOAD_PATH.glob("*"))
    return Response({
        "download_path": str(DOWNLOAD_PATH),
        "path_exists": DOWNLOAD_PATH.exists(),
        "path_writable": os.access(DOWNLOAD_PATH, os.W_OK),
        "files_count": len(files_in_dir),
        "recent_files": [f.name for f in sorted(files_in_dir, key=lambda x: x.stat().st_mtime)[-10:]],
        "yt_dlp_version": yt_dlp.version.__version__,
        "working_directory": os.getcwd()
    })

def check_platform_support(request):
    """Check platform support and provide details about download capabilities"""
    return Response({
        "supported_platforms": [
            "YouTube", 
            "TikTok", 
            "Twitter/X", 
            "Instagram"
        ],
        "download_options": {
            "resolutions": [
                "360p", 
                "480p", 
                "720p", 
                "1080p", 
                "best"
            ],
            "types": [
                "video", 
                "playlist"
            ]
        },
        "debug_info": {
            "download_path": str(DOWNLOAD_PATH),
            "path_exists": DOWNLOAD_PATH.exists(),
            "files_in_directory": len(list(DOWNLOAD_PATH.glob("*")))
        },
        "notes": [
            "Auto-detection of platform supported",
            "Fallback resolution available",
            "Progress tracking enabled",
            "Enhanced error logging"
        ]
    })