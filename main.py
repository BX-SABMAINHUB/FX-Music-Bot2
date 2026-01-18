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
        print(f"✅ FLEXUS ULTRA-HD conectado como {self.user}")

bot = FlexusBot()

# --- CONFIGURACIÓN DE AUDIO DE ÉLITE (MÁXIMA CALIDAD CONSTANTE) ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

# Aquí forzamos 320kbps constantes y el codec libopus para que no baje la calidad
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -acodec libopus -b:a 512k -vbr off -compression_level 10',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

@bot.tree.command(name="play", description="Reproduce música en ULTRA-HD constante")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        if 'entries' in data: data = data['entries'][0]
        
        url, titulo = data['url'], data['title']
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()

        # Ajuste de volumen maestro para que suene FUERTE
        audio_source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        high_quality_source = discord.PCMVolumeTransformer(audio_source, volume=1.5) # 1.5 es 150% de volumen base

        if vc.is_playing():
            bot.queue.append((url, titulo))
            await interaction.followup.send(f"✅ En cola (HD): **{titulo}**")
        else:
            vc.play(high_quality_source)
            await interaction.followup.send(f"🔊 Sonando en Máxima Calidad: **{titulo}**")
    except Exception as e:
        await interaction.followup.send("❌ Error de audio.")

# --- LOS DEMÁS COMANDOS (SE MANTIENEN IGUAL PARA NO ROMPER NADA) ---

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Reanuda la música")
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

@bot.tree.command(name="stop", description="Desconectar")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="queue", description="Ver cola")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("📝 Vacía.")
    lista = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)])
    await interaction.response.send_message(f"📋 **Cola:**\n{lista}")

@bot.tree.command(name="volume", description="Volumen (1-100)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen: {nivel}%")

@bot.tree.command(name="clear", description="Vaciar cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Limpio.")

@bot.tree.command(name="reconnect", description="Reset de audio")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("🔄 Reiniciado.")

@bot.tree.command(name="now", description="Info actual")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔎 Sonando ahora mismo.")

bot.run(TOKEN)
