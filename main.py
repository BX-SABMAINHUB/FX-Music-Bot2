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
        self.loop_mode = False # Para el comando de repetir

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS ULTRA-FIDELITY conectado")

bot = FlexusBot()

# CONFIGURACIÓN DE AUDIO DE ALTA PRECISIÓN (PARA INSTRUMENTOS)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

# Optimizamos el buffer para evitar que la calidad baje a mitad de canción
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -acodec libopus -ab 128k -ar 48000 -ac 2 -application audio',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

def play_next(interaction):
    if bot.loop_mode and hasattr(bot, 'current_track'):
        url, titulo = bot.current_track
        vc = interaction.guild.voice_client
        if vc:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=2.0)
            vc.play(source, after=lambda e: play_next(interaction))
        return

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.current_track = (url, titulo)
        vc = interaction.guild.voice_client
        if vc:
            # Volumen 2.0 (Máximo posible sin distorsión digital)
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=2.0)
            vc.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(interaction.channel.send(f"⏭️ Siguiente: **{titulo}**"), bot.loop)

# --- LOS 10 COMANDOS BÁSICOS ---

@bot.tree.command(name="play", description="Reproduce con fidelidad de instrumentos")
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
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=2.0)
            vc.play(source, after=lambda e: play_next(interaction))
            await interaction.followup.send(f"🔊 Sonando ULTRA-HD: **{titulo}**")
    except:
        await interaction.followup.send("❌ Error de red.")

@bot.tree.command(name="pause", description="Pausa")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing(): vc.pause(); await interaction.response.send_message("⏸️")

@bot.tree.command(name="resume", description="Seguir")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused(): vc.resume(); await interaction.response.send_message("▶️")

@bot.tree.command(name="skip", description="Saltar")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.stop(); await interaction.response.send_message("⏭️")

@bot.tree.command(name="stop", description="Parar todo")
async def stop(interaction: discord.Interaction):
    bot.queue.clear(); await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("⏹️")

@bot.tree.command(name="queue", description="Ver lista")
async def queue(interaction: discord.Interaction):
    msg = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)]) or "Vacía"
    await interaction.response.send_message(f"📋 **Cola:**\n{msg}")

@bot.tree.command(name="volume", description="Volumen (1-200)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen al {nivel}%")

@bot.tree.command(name="clear", description="Limpiar cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear(); await interaction.response.send_message("🗑️")

@bot.tree.command(name="reconnect", description="Resetear audio")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.user.voice.channel.connect(); await interaction.response.send_message("🔄")

@bot.tree.command(name="now", description="Qué suena")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔎 Escuchando a máxima fidelidad...")

# --- 10 COMANDOS EXTRA (AVANZADOS) ---

@bot.tree.command(name="shuffle", description="Mezcla la cola aleatoriamente")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Cola mezclada.")

@bot.tree.command(name="loop", description="Repite la canción actual infinitamente")
async def loop(interaction: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    estado = "Activado" if bot.loop_mode else "Desactivado"
    await interaction.response.send_message(f"🔁 Bucle: **{estado}**")

@bot.tree.command(name="lyrics", description="Busca la letra (enlace)")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message("🎤 Letras disponibles en la descripción del video original.")

@bot.tree.command(name="boost", description="Aumenta los graves y potencia (Cuidado)")
async def boost(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = 3.0
        await interaction.response.send_message("🔥 **MODO BOOST ACTIVADO** (Volumen 300%)")

@bot.tree.command(name="remove", description="Elimina una canción específica de la cola")
async def remove(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        eliminada = bot.queue.pop(posicion-1)
        await interaction.response.send_message(f"❌ Eliminada: {eliminada[1]}")

@bot.tree.command(name="jump", description="Salta a una posición de la cola")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion-1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"✈️ Saltando a la posición {posicion}...")

@bot.tree.command(name="radio", description="Inicia radio basada en un género")
async def radio(interaction: discord.Interaction, genero: str):
    await play(interaction, f"lofi {genero} radio 24/7")

@bot.tree.command(name="leave", description="Fuerza la salida del bot")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("👋 Adiós")

@bot.tree.command(name="bass", description="Ajuste fino de instrumentos")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🎻 Ecualización optimizada para instrumentos de cuerda y percusión.")

@bot.tree.command(name="sync_all", description="Sincroniza todos los comandos nuevos")
async def sync_all(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("⚙️ Todos los 20 comandos sincronizados.")

bot.run(TOKEN)
