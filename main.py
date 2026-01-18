import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")

class FlexusBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="fx!", intents=intents)
        self.queue = []

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS MAX-QUALITY conectado")

bot = FlexusBot()

# --- CONFIGURACIÓN DE AUDIO PROFESIONAL ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

# Bitrate de 192k: El punto dulce para máxima fidelidad sin que se corte el audio
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -acodec libopus -ab 192k -ar 48000 -ac 2',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

@bot.tree.command(name="play", description="Reproduce música a Calidad Máxima")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        if 'entries' in data: data = data['entries'][0]
        
        url, titulo = data['url'], data['title']
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()

        # Volumen al 150% para que suene FUERTE desde el inicio
        audio_source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        vc_source = discord.PCMVolumeTransformer(audio_source, volume=1.5)

        if vc.is_playing():
            bot.queue.append((url, titulo))
            await interaction.followup.send(f"✅ Añadida a la cola: **{titulo}**")
        else:
            vc.play(vc_source)
            await interaction.followup.send(f"🔊 Sonando ahora en HD: **{titulo}**")
    except Exception as e:
        await interaction.followup.send("❌ Error al reproducir. Reintentando...")

# --- LOS 10 COMANDOS DE MÚSICA (CORREGIDOS) ---

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction): # Error de duplicación corregido aquí
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Música pausada.")
    else:
        await interaction.response.send_message("❌ No hay nada sonando.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Música reanudada.")

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Canción saltada.")

@bot.tree.command(name="stop", description="Limpia la cola y saca al bot")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="queue", description="Muestra la lista de espera")
async def queue(interaction: discord.Interaction):
    if not bot.queue:
        return await interaction.response.send_message("📝 La cola está vacía.")
    lista = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)])
    await interaction.response.send_message(f"📋 **Cola actual:**\n{lista}")

@bot.tree.command(name="volume", description="Ajusta el volumen (1-100)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen ajustado al {nivel}%")

@bot.tree.command(name="clear", description="Vacía la cola de reproducción")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada.")

@bot.tree.command(name="reconnect", description="Reinicia la conexión si el audio se corta")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("🔄 Conexión de audio reiniciada.")

@bot.tree.command(name="now", description="Muestra qué canción suena ahora")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔎 Comprobando estado del reproductor...")

bot.run(TOKEN)
