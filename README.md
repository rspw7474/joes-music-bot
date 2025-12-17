# About
Joe's Music Bot is a Discord bot for streaming music (and other audio) from YouTube to a voice channel.
<br><br>

# Setup
### Invite the bot to a Discord server.
1. Click this [invite link.](https://discord.com/oauth2/authorize?client_id=1445110325866270792&permissions=3145728&integration_type=0&scope=bot)
2. Select the Discord server to which you want to invite the bot.
3. Click `Continue`.
4. Ensure the `Connect` and `Speak` permissions are selected.
5. Click `Authorize`.

### Integrations (optional)
To configure integrations:
1. Right-click the server icon or name.
2. Hover over `Server Settings`.
3. Click `Integrations`.
4. Under `Bots and Apps`, click `Joe's Music Bot`.
5. From this menu, you can configure the bot so its commands can only be run by certain members or in certain text channels.
<br><br>

# Usage
#### `/help`
Show all commands.

#### `/play` `<url>`
Play music given a YouTube URL.

#### `/pause`
Pause the current track.

#### `/resume`
Resume the paused track.

#### `/loop`
Toggle looping.

#### `/queue`
Show the queue.

#### `/skip`
Skip the current track.

#### `/clear`
Clear the queue

#### `/leave`
Stop the current track, clear the queue, and disconnect.
<br><br>

# Built Using
### discord.py
- [repository](https://github.com/Rapptz/discord.py)
- [documentation](https://discordpy.readthedocs.io/en/stable/)
### ffmpeg
- [repository](https://github.com/FFmpeg/FFmpeg)
- [documentation](https://ffmpeg.org/ffmpeg.html)
### yt-dlp
- [repository](https://github.com/yt-dlp/yt-dlp)
- [documentation](https://pypi.org/project/yt-dlp/)
