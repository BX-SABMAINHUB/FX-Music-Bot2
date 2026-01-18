import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import random
import os  # Importante para leer la variable de Railway

# --- CONFIGURACIÓN SEGURA ---
# Aquí le decimos al bot que busque la "llave" en Railway, no en el texto
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
        print(f"✅ FLEXUS Conectado Correctamente")

bot = MusicBot()

# --- MOTOR DE AUDIO ---
async def get_audio_data(query):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
    if 'entries' in data: data = data['entries'][0]
    return {'url': data['url'], 'title': data['title']}

def play_next(interaction, guild_id):
    if guild_id in bot.queues and bot.queues[guild_id]:
        song = bot.queues[guild_id].pop(0)
        vc = interaction.guild.voice_client
        if vc:
            vc.play(discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS), 
                    after=lambda e: play_next(interaction, guild_id))
            asyncio.run_coroutine_threadsafe(interaction.channel.send(f"🎶 Reproduciendo: **{song['title']}**"), bot.loop)

# --- COMANDOS ---
@bot.tree.command(name="play", description="Reproduce música")
async def play(interaction: discord.Interaction, cancion: str, artista: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ ¡Entra a un canal de voz!", ephemeral=True)
    
    await interaction.response.defer()
    query = f"{cancion} {artista}"
    
    try:
        info = await get_audio_data(query)
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        gid = interaction.guild.id
        if gid not in bot.queues: bot.queues[gid] = []

        if vc.is_playing():
            bot.queues[gid].append(info)
            await interaction.followup.send(f"⌛ En cola: **{info['title']}**")
        else:
            vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), 
                    after=lambda e: play_next(interaction, gid))
            await interaction.followup.send(f"▶️ Sonando: **{info['title']}**")
    except:
        await interaction.followup.send("❌ Error al buscar la canción.")

@bot.tree.command(name="stop", description="Detiene la música")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        bot.queues[interaction.guild.id] = []
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏹️ Música detenida.")

@bot.tree.command(name="leave", description="Saca al bot")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 ¡Adiós!")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Sincronizado.")

bot.run(TOKEN)
