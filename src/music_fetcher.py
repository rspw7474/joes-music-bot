import asyncio
import discord
import os
import yaml
import yt_dlp

import logging
logger = logging.getLogger(__name__)


class MusicFetcher:
    def __init__(self) -> None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file_path = f"{root}/config/music_config.yaml"
        with open(config_file_path, "r") as f:
            config = yaml.safe_load(f)

        self.ffmpeg_options: dict = config.get("ffmpeg_options", {})
        self.ydl_options: dict = config.get("ydl_options", {})

    def extract_info(self, url: str) -> dict | None:
        try:
            with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except yt_dlp.utils.DownloadError as e:
            logger.error(e)
        except Exception as e:
            logger.exception(e)

        return None

    async def fetch_title(self, url: str) -> str:
        info = await asyncio.to_thread(self.extract_info, url)
        if not info:
            return "Unknown Title"
        return info.get("title", "Unknown Title")

    async def fetch_source(self, url: str) -> discord.AudioSource | None:
        info = await asyncio.to_thread(self.extract_info, url)
        if not info:
            return None

        source_url = info.get("url")
        if not source_url:
            return None

        source = discord.FFmpegOpusAudio(source_url, **self.ffmpeg_options)
        return source
