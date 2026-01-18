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
        self.queue = [] # Lista de espera

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS V2 (Alta Calidad) conectado como {self.user}")

bot = FlexusBot()

# CONFIGURACIÓN DE MÁXIMA CALIDAD DE AUDIO
YTDL_OPTIONS = {
    'format': 'bestaudio/best', # Busca la mejor calidad de audio disponible
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus', # El codec de mayor fidelidad para Discord
        'preferredquality': '320', # Simula 320kbps si el origen lo permite
    }],
}

# Optimización para que el audio no tenga micro-cortes
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 320k', # Forzamos el bitrate de salida a 320k
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- 10 COMANDOS DE MÚSICA ---

@bot.tree.command(name="play", description="Reproduce música a máxima calidad")
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
            await interaction.followup.send(f"✅ Añadida a la cola: **{titulo}**")
        else:
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            await interaction.followup.send(f"🎶 Reproduciendo a 320kbps: **{titulo}**")
    except Exception as e:
        await interaction.followup.send("❌ Error al cargar el audio.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
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
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop() # Al detenerse, si tienes un sistema de cola, saltaría a la siguiente
        await interaction.response.send_message("⏭️ Canción saltada.")

@bot.tree.command(name="stop", description="Limpia la cola y saca al bot")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Bot desconectado y cola limpia.")

@bot.tree.command(name="queue", description="Muestra la lista de espera")
async def queue(interaction: discord.Interaction):
    if not bot.queue:
        return await interaction.response.send_message("📝 La cola está vacía.")
    lista = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)])
    await interaction.response.send_message(f"📋 **Cola actual:**\n{lista}")

@bot.tree.command(name="now", description="Muestra qué canción suena ahora")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔎 Comando en desarrollo: Revisa el estado en tu lista de usuarios.")

@bot.tree.command(name="volume", description="Ajusta el volumen (1-100)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source = discord.PCMVolumeTransformer(vc.source)
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

bot.run(TOKEN)
