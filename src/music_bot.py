import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import os
import traceback
import yaml

from models import Track
from music_fetcher import MusicFetcher
from music_player import MusicPlayer

import logging
logger = logging.getLogger(__name__)


class MusicBot(commands.Bot):
    # ================================================================ #
    # Configuration                                                    #
    # ================================================================ #
    def __init__(self) -> None:
        super().__init__(command_prefix="", intents=discord.Intents.default())
        self.messages: dict[str, str] = {}
        self.music_fetcher = MusicFetcher()
        self.music_players: dict[int, MusicPlayer] = {}
        self.music_player_locks: dict[int, asyncio.Lock] = {}

    def run(self) -> None:
        token = os.getenv("JMB_TOKEN")
        if not token:
            logger.error("Token not found. Shutting down...")
            exit()

        super().run(token, log_handler=None)

    async def setup_hook(self) -> None:
        self.configure()
        self.add_commands()
        self.tree.on_error = self.on_app_command_error
        await self.tree.sync()

    def configure(self) -> None:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_file_path = f"{root}/config/bot_config.yaml"
        with open(config_file_path, "r") as f:
            config = yaml.safe_load(f)

        self.messages = config.get("messages", {})

    def add_commands(self) -> None:
        self.tree.add_command(app_commands.Command(
            name="play",
            description="Play track given a YouTube URL.",
            callback=self.play_command
        ))
        self.tree.add_command(app_commands.Command(
            name="pause",
            description="Pause the current track.",
            callback=self.pause_command
        ))
        self.tree.add_command(app_commands.Command(
            name="resume",
            description="Resume the paused track.",
            callback=self.resume_command
        ))
        self.tree.add_command(app_commands.Command(
            name="loop",
            description="Toggle looping.",
            callback=self.loop_command
        ))
        self.tree.add_command(app_commands.Command(
            name="queue",
            description="Show the queue.",
            callback=self.queue_command
        ))
        self.tree.add_command(app_commands.Command(
            name="skip",
            description="Skip the current track.",
            callback=self.skip_command
        ))
        self.tree.add_command(app_commands.Command(
            name="clear",
            description="Clear the queue.",
            callback=self.clear_command
        ))
        self.tree.add_command(app_commands.Command(
            name="leave",
            description="Stop the current track, clear the queue, and disconnect.",
            callback=self.leave_command
        ))
        self.tree.add_command(app_commands.Command(
            name="help",
            description="Show all commands.",
            callback=self.help_commandj
        ))

    # ================================================================ #
    # Event Handlers                                                   #
    # ================================================================ #
    async def on_ready(self) -> None:
        logger.info(f"{self.user} successfully started.")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(f"{guild.name} invited bot.")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info(f"{guild.name} kicked bot.")
        await self.delete_music_player(guild.id)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return

        voice_client = self.get_voice_client(member.guild)
        if not voice_client:
            return

        voice_channel = voice_client.channel
        if not voice_channel:
            return

        if len(voice_channel.members) == 1:
            await self.delete_music_player(member.guild.id)
            await voice_client.disconnect()

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        logger.exception(error)
        if not interaction:
            return

        if interaction.is_expired():
            return

        if isinstance(error, app_commands.MissingPermissions):
            message = self.messages.get("error_permissions", "Missing permissions.")
        elif isinstance(error, app_commands.CommandInvokeError):
            message = self.messages.get("error_command", "Something went wrong while running your command.")
        else:
            message = self.messages.get("error_unknown", "An unknown error occurred.")

        await self.safe_followup(interaction, message)

    # ================================================================ #
    # Helpers                                                          #
    # ================================================================ #
    async def safe_followup(self, interaction: discord.Interaction, message: str) -> None:
        if not interaction or interaction.is_expired() or not isinstance(message, str):
            logger.warning(self.messages.get("error_interaction", "Invalid interaction."))
            return

        if not interaction.response.is_done():
            await interaction.response.send_message(message)
        else:
            await interaction.followup.send(message)

    def get_voice_client(self, guild: discord.Guild) -> discord.VoiceClient | None:
        voice_client = discord.utils.get(self.voice_clients, guild=guild)
        return voice_client

    async def get_music_player(self, guild_id: int) -> MusicPlayer:
        lock = self.music_player_locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            music_player = self.music_players.get(guild_id)
            if music_player and music_player.is_running():
                return music_player

            if music_player:
                await music_player.shutdown()

            music_player = MusicPlayer(self, guild_id)
            self.music_players[guild_id] = music_player
            return music_player

    async def delete_music_player(self, guild_id: int) -> None:
        music_player = self.music_players.pop(guild_id, None)
        if music_player:
            await music_player.shutdown()

        self.music_player_locks.pop(guild_id, None)

    # ================================================================ #
    # Commands                                                         #
    # ================================================================ #
    async def play_command(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer(thinking=True)

        if not interaction.user.voice or not interaction.user.voice.channel:
            message = self.messages.get("event_user_voiceless", "You're not in a voice channel.")
            await interaction.followup.send(message)
            return

        permissions = interaction.user.voice.channel.permissions_for(interaction.guild.me)
        if not permissions.connect or not permissions.speak:
            message = self.messages.get("error_permissions", "I don't have permission to do that.")
            await interaction.followup.send(message)
            return

        voice_client = self.get_voice_client(interaction.guild)
        if not voice_client:
            voice_client = await interaction.user.voice.channel.connect()
        elif voice_client.channel != interaction.user.voice.channel:
            await voice_client.move_to(interaction.user.voice.channel)

        message = self.messages.get("event_play", "Working...")
        await interaction.followup.send(message)

        title = await self.music_fetcher.fetch_title(url)
        if title == "Unknown Title":
            text_channel = interaction.channel
            message = self.messages.get("error_download", "I couldn't find that video.")
            await text_channel.send(message)
            return

        music_player = await self.get_music_player(interaction.guild.id)
        track = Track(url=url, title=title, text_channel_id=interaction.channel.id)
        await music_player.enqueue(track)

        text_channel = interaction.channel
        message = f"Queued: `{title}`"
        await text_channel.send(message)

    async def pause_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        voice_client = self.get_voice_client(interaction.guild)
        if not voice_client or not voice_client.is_connected():
            message = self.messages.get("event_bot_voiceless", "I'm not in a voice channel.")
            await interaction.followup.send(message)
            return

        if not voice_client.is_playing():
            message = self.messages.get("event_not_playing", "I'm not playing anything.")
            await interaction.followup.send(message)
            return

        music_player = await self.get_music_player(interaction.guild.id)
        await music_player.pause()

        message = self.messages.get("event_track_paused", "Paused.")
        await interaction.followup.send(message)

    async def resume_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        voice_client = self.get_voice_client(interaction.guild)
        if not voice_client or not voice_client.is_connected():
            message = self.messages.get("event_bot_voiceless", "I'm not in a voice channel.")
            await interaction.followup.send(message)
            return

        if not voice_client.is_paused():
            message = self.messages.get("event_not_paused", "I'm not paused.")
            await interaction.followup.send(message)
            return

        music_player = await self.get_music_player(interaction.guild.id)
        await music_player.resume()

        message = self.messages.get("event_track_resumed", "Resumed.")
        await interaction.followup.send(message)

    async def loop_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        voice_client = self.get_voice_client(interaction.guild)
        if not voice_client or not voice_client.is_connected():
            message = self.messages.get("event_bot_voiceless", "I'm not in a voice channel.")
            await interaction.followup.send(message)
            return

        music_player = await self.get_music_player(interaction.guild.id)
        music_player.toggle_looping()

        if music_player.is_looping:
            message = self.messages.get("event_looping_enabled", "Looping enabled.")
        else:
            message = self.messages.get("event_looping_disabled", "Looping disabled.")
        await interaction.followup.send(message)

    async def queue_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        music_player = await self.get_music_player(interaction.guild.id)
        if music_player.is_queue_empty():
            message = self.messages.get("event_queue_empty", "The queue is empty.")
            await interaction.followup.send(message)
            return

        message = f"__Queue__\n" + "\n".join([f"`{track.title}`" for track in music_player.get_queue()])
        await interaction.followup.send(message)

    async def skip_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        voice_client = self.get_voice_client(interaction.guild)
        if not voice_client or not voice_client.is_connected():
            message = self.messages.get("event_bot_voiceless", "I'm not in a voice channel.")
            await interaction.followup.send(message)
            return

        if not voice_client.is_playing() and not voice_client.is_paused():
            message = self.messages.get("event_not_playing", "I'm not playing anything.")
            await interaction.followup.send(message)
            return

        music_player = await self.get_music_player(interaction.guild.id)
        await music_player.skip()

        message = self.messages.get("event_track_skipped", "Skipped.")
        await interaction.followup.send(message)

    async def clear_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        music_player = await self.get_music_player(interaction.guild.id)
        if music_player.is_queue_empty():
            message = self.messages.get("event_queue_empty", "The queue is empty.")
            await interaction.followup.send(message)
            return

        await music_player.clear()

        message = self.messages.get("event_queue_cleared", "Queue cleared.")
        await interaction.followup.send(message)

    async def leave_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        voice_client = self.get_voice_client(interaction.guild)
        if not voice_client or not voice_client.is_connected():
            message = self.messages.get("event_bot_voiceless", "I'm not in a voice channel.")
            await interaction.followup.send(message)
            return

        await self.delete_music_player(interaction.guild.id)

        voice_client = self.get_voice_client(interaction.guild)
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()

        message = self.messages.get("event_leave", "Bye.")
        await interaction.followup.send(message)

    async def help_commandj(self, interaction: discord.Interaction) -> None:
        message = self.messages.get("help", "I can't help you.")
        await interaction.response.send_message(message)
