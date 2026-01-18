import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os

# 1. DEFINICIÓN DEL BOT (Estable como en IMG_0139)
TOKEN = os.getenv("DISCORD_TOKEN")

class FlexusBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="fx!", intents=intents)
        self.queue = [] 

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS conectado y estable")

bot = FlexusBot()

# 2. CONFIGURACIÓN DE AUDIO (La que funcionaba en IMG_0137)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# 3. LOS 10 COMANDOS DE MÚSICA
@bot.tree.command(name="play", description="Reproduce música")
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
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            await interaction.followup.send(f"🎶 Sonando: **{titulo}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error al reproducir.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Sigue la música")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="skip", description="Siguiente canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop", description="Desconectar bot")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="queue", description="Ver la cola")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("📝 Cola vacía.")
    lista = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)])
    await interaction.response.send_message(f"📋 **Cola:**\n{lista}")

@bot.tree.command(name="volume", description="Ajustar volumen (1-100)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source = discord.PCMVolumeTransformer(vc.source)
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen: {nivel}%")

@bot.tree.command(name="clear", description="Limpiar cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada.")

@bot.tree.command(name="reconnect", description="Reiniciar conexión")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("🔄 Reiniciado.")

@bot.tree.command(name="now", description="Canción actual")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔎 Comprobando canción...")

bot.run(TOKEN)
