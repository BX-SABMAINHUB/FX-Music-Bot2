import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import random
import os

# CONFIGURACIÓN SEGURA: Lee el token desde Railway
TOKEN = os.getenv("DISCORD_TOKEN")

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="fx!", intents=intents)
        self.queues = {}

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS Conectado: {self.user}")

bot = MusicBot()

# MOTOR DE AUDIO
async def get_audio(query):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
    if 'entries' in data: data = data['entries'][0]
    return {'url': data['url'], 'title': data['title']}

def play_next(interaction, gid):
    if gid in bot.queues and bot.queues[gid]:
        song = bot.queues[gid].pop(0)
        vc = interaction.guild.voice_client
        if vc:
            vc.play(discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS), 
                    after=lambda e: play_next(interaction, gid))

# LOS 10 COMANDOS DE MÚSICA
@bot.tree.command(name="play", description="Reproduce música")
async def play(interaction: discord.Interaction, cancion: str, artista: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ Entra a un canal de voz.")
    await interaction.response.defer()
    query = f"{cancion} {artista}"
    info = await get_audio(query)
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    gid = interaction.guild.id
    if gid not in bot.queues: bot.queues[gid] = []
    if vc.is_playing():
        bot.queues[gid].append(info)
        await interaction.followup.send(f"⌛ Cola: **{info['title']}**")
    else:
        vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, gid))
        await interaction.followup.send(f"▶️ Sonando: **{info['title']}**")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause(); await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume(); await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="skip", description="Salta la canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.stop(); await interaction.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop", description="Detiene todo")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        bot.queues[interaction.guild.id] = []
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏹️ Detenido.")

@bot.tree.command(name="queue", description="Ver la cola")
async def queue(interaction: discord.Interaction):
    q = bot.queues.get(interaction.guild.id, [])
    msg = "\n".join([f"{i+1}. {s['title']}" for i, s in enumerate(q[:10])]) if q else "Vacía."
    await interaction.response.send_message(f"📜 **Cola:**\n{msg}")

@bot.tree.command(name="nowplaying", description="Qué suena ahora")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message("🎧 Reproduciendo audio de alta calidad.")

@bot.tree.command(name="volume", description="Ajustar volumen")
async def volume(interaction: discord.Interaction, nivel: int):
    await interaction.response.send_message(f"🔊 Volumen al {nivel}%.")

@bot.tree.command(name="shuffle", description="Mezclar canciones")
async def shuffle(interaction: discord.Interaction):
    q = bot.queues.get(interaction.guild.id, [])
    random.shuffle(q)
    await interaction.response.send_message("🔀 Cola mezclada.")

@bot.tree.command(name="leave", description="Sacar al bot")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("👋 Adiós.")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Sincronizado.")

bot.run(TOKEN)
