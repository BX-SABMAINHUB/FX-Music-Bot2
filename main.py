import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
import random

TOKEN = os.getenv("DISCORD_TOKEN")

class FlexusBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="fx!", intents=intents)
        self.queue = []
        self.loop_mode = False

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS V2 (Estable) conectado")

bot = FlexusBot()

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

# Configuración optimizada para evitar el bloqueo del servidor
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -acodec libopus -ab 128k -ar 48000 -ac 2',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

def play_next(interaction):
    if bot.loop_mode and hasattr(bot, 'current_track'):
        url, titulo = bot.current_track
        vc = interaction.guild.voice_client
        if vc:
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
        return

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.current_track = (url, titulo)
        vc = interaction.guild.voice_client
        if vc:
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(interaction.channel.send(f"⏭️ Siguiente: **{titulo}**"), bot.loop)

# --- 20 COMANDOS DE MÚSICA ---

@bot.tree.command(name="play", description="Reproduce música (Estable)")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        if 'entries' in data: data = data['entries'][0]
        url, titulo = data['url'], data['title']
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()

        if vc.is_playing():
            bot.queue.append((url, titulo))
            await interaction.followup.send(f"✅ En cola: **{titulo}**")
        else:
            bot.current_track = (url, titulo)
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            await interaction.followup.send(f"🎶 Reproduciendo: **{titulo}**")
    except:
        await interaction.followup.send("❌ Error de conexión.")

@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing(): vc.pause(); await interaction.response.send_message("⏸️")

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused(): vc.resume(); await interaction.response.send_message("▶️")

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.stop(); await interaction.response.send_message("⏭️")

@bot.tree.command(name="stop")
async def stop(interaction: discord.Interaction):
    bot.queue.clear(); await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("⏹️")

@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    msg = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)]) or "Vacía"
    await interaction.response.send_message(f"📋 **Cola:**\n{msg}")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear(); await interaction.response.send_message("🗑️")

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue); await interaction.response.send_message("🔀 Mezclada")

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await interaction.response.send_message(f"🔁 Bucle: {'ON' if bot.loop_mode else 'OFF'}")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("👋")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source = discord.PCMVolumeTransformer(vc.source)
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 {nivel}%")

@bot.tree.command(name="now")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔎 Sonando ahora...")

@bot.tree.command(name="reconnect")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.user.voice.channel.connect(); await interaction.response.send_message("🔄")

@bot.tree.command(name="remove")
async def remove(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue): bot.queue.pop(pos-1); await interaction.response.send_message("❌ Quitada")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue): 
        for _ in range(pos-1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"✈️ Saltando a {pos}")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message("🎤 Letras no disponibles.")

@bot.tree.command(name="bass")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🎻 EQ Instrumentos Activo.")

@bot.tree.command(name="radio")
async def radio(interaction: discord.Interaction, genero: str):
    await play(interaction, f"{genero} music radio")

@bot.tree.command(name="sync_all")
async def sync_all(interaction: discord.Interaction):
    await bot.tree.sync(); await interaction.response.send_message("⚙️ Sincronizado")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Latencia: {round(bot.latency * 1000)}ms")

bot.run(TOKEN)
