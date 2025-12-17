import asyncio
from collections import deque
import discord
from discord.ext import commands

from models import Track

import logging
logger = logging.getLogger(__name__)


class MusicPlayer:
    def __init__(self, bot: commands.Bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id

        self.lock = asyncio.Lock()
        self.is_looping: bool = False
        self.queue: deque[Track] = deque()
        self.queue_condition = asyncio.Condition()
        self.shutdown_event = asyncio.Event()
        self.track_done_event = asyncio.Event()
        self.task = asyncio.create_task(self.run(), name=f"MusicPlayer_{guild_id}")

    @property
    def voice_client(self) -> discord.VoiceClient | None:
        return discord.utils.get(self.bot.voice_clients, guild__id=self.guild_id)

    # ================================================================ #
    # Main Loop                                                        #
    # ================================================================ #
    async def run(self) -> None:
        await self.bot.wait_until_ready()
        try:
            while not self.shutdown_event.is_set():
                async with self.queue_condition:
                    await self.queue_condition.wait_for(lambda: self.queue or self.shutdown_event.is_set())

                    if self.shutdown_event.is_set():
                        break

                    track = self.queue.popleft()

                while True:
                    await self.play_track(track)
                    if self.shutdown_event.is_set() or not self.is_looping:
                        break

        except asyncio.CancelledError:
            logger.info(f"{self.task.get_name()} cancelled.")
        except Exception as e:
            logger.exception(e)

    # ================================================================ #
    # Main Loop Internals                                              #
    # ================================================================ #
    async def play_track(self, track: Track) -> None:
        self.track_done_event.clear()

        def after_callback(error: Exception | None) -> None:
            if error:
                logger.error(error)
            self.bot.loop.call_soon_threadsafe(self.track_done_event.set)

        audio_source = await self.bot.music_fetcher.fetch_source(track.url)
        if not audio_source:
            text_channel = self.bot.get_channel(track.text_channel_id)
            if text_channel:
                message = self.bot.messages.get("error_source", "I couldn't find an audio source for that video.")
                await text_channel.send(message)
            return

        await asyncio.sleep(3)
        async with self.lock:
            voice_client = self.voice_client
            if not voice_client or not voice_client.is_connected():
                self.track_done_event.set()
                return

            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()

            voice_client.play(audio_source, after=after_callback)

        text_channel = self.bot.get_channel(track.text_channel_id)
        if text_channel:
            message = f"Now playing:\n{track.url}"
            await text_channel.send(message)

        await self.track_done_event.wait()

    # ================================================================ #
    # State Inspectors                                                 #
    # ================================================================ #
    def is_running(self) -> bool:
        return not self.task.done()

    def is_queue_empty(self) -> bool:
        return not self.queue

    def get_queue(self) -> list[Track]:
        return list(self.queue)

    # ================================================================ #
    # Playback Controllers                                             #
    # ================================================================ #
    async def pause(self) -> None:
        async with self.lock:
            voice_client = self.voice_client
            if voice_client and voice_client.is_connected() and voice_client.is_playing():
                voice_client.pause()

    async def resume(self) -> None:
        async with self.lock:
            voice_client = self.voice_client
            if voice_client and voice_client.is_connected() and voice_client.is_paused():
                voice_client.resume()

    async def stop(self) -> None:
        async with self.lock:
            voice_client = self.voice_client
            if voice_client and voice_client.is_connected():
                voice_client.stop()

    def toggle_looping(self) -> None:
        self.is_looping = not self.is_looping

    # ================================================================ #
    # Queue Managers                                                   #
    # ================================================================ #
    async def enqueue(self, track: Track) -> None:
        async with self.queue_condition:
            self.queue.append(track)
            self.queue_condition.notify()

    async def skip(self) -> None:
        self.is_looping = False
        await self.stop()

    async def clear(self) -> None:
        async with self.queue_condition:
            self.queue.clear()

    # ================================================================ #
    # Shutdown                                                         #
    # ================================================================ #
    async def shutdown(self) -> None:
        self.is_looping = False
        await self.clear()
        await self.stop()
        self.shutdown_event.set()
        async with self.queue_condition:
            self.queue_condition.notify_all()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
