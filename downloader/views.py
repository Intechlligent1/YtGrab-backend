import os
from pathlib import Path
from rest_framework.response import Response
from rest_framework.decorators import api_view
import yt_dlp

DOWNLOAD_PATH = Path.home() / "Videos" / "IntechDownloader"
DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True) 

@api_view(['POST'])
def download_video(request):
    url = request.data.get('url')
    resolution = request.data.get('resolution', '1080p')
    download_type = request.data.get('download_type', 'video') 
    fallback_resolution = request.data.get('fallback_resolution', '720p')

    if not url:
        return Response({"error": "URL is required"}, status=400)

    format_map = {
        "best": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[ext=mp4]/best",
        "720p": "bestvideo[height<=720]+bestaudio/best[ext=mp4]/best",
        "480p": "bestvideo[height<=480]+bestaudio/best[ext=mp4]/best",
        "360p": "bestvideo[height<=360]+bestaudio/best[ext=mp4]/best",
    }

    ydl_opts = {
        'format': format_map.get(resolution, format_map['1080p']),
        'outtmpl': str(DOWNLOAD_PATH / "%(title)s.%(ext)s"),
        'noplaylist': download_type != 'playlist',
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }, {
            'key': 'FFmpegEmbedSubtitle',
        }],
        'verbose': True,
        'ignoreerrors': True,
        'geo_bypass': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if 'entries' in info:
                successful_downloads = []
                failed_downloads = []
                
                for entry in info.get('entries', []):
                    if entry:
                        successful_downloads.append({
                            'title': entry.get('title', 'Unknown'),
                            'resolution': entry.get('height', 'Unknown'),
                            'format': entry.get('format', 'Unknown')
                        })
                    else:
                        failed_downloads.append('Unknown (extraction failed)')
                
                return Response({
                    "message": f"Playlist downloaded successfully ({len(successful_downloads)} videos)",
                    "successful": successful_downloads,
                    "failed": failed_downloads
                })
            else:
                return Response({
                    "message": "Download successful", 
                    "title": info.get('title'), 
                    "resolution": info.get('height')
                })
    except Exception as e:
        # If primary resolution fails, try fallback
        if resolution != fallback_resolution and fallback_resolution in format_map:
            ydl_opts['format'] = format_map[fallback_resolution]
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return Response({
                        "message": f"Download successful with fallback resolution ({fallback_resolution})",
                        "title": info.get('title') if 'entries' not in info else f"Playlist with {len(info.get('entries', []))} videos"
                    })
            except Exception as fallback_error:
                return Response({"error": f"Download failed: {str(fallback_error)}"}, status=500)
        return Response({"error": f"Download failed: {str(e)}"}, status=500)