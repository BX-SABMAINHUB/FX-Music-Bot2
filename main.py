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
        # Usamos prefijo "!" para que funcione !help
        super().__init__(command_prefix="!", intents=intents)
        self.queue = [] 
        self.playlists = {} # Diccionario para guardar tus playlists

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS V2 (Alta Calidad) conectado como {self.user}")

bot = FlexusBot()

# --- TU CONFIGURACIÓN DE MÁXIMA CALIDAD (TAL CUAL ME LA DISTE) ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',
        'preferredquality': '320',
    }],
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 320k',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- FUNCIÓN PARA QUE LA COLA NO SE PARE (EL ARREGLO) ---
def check_queue(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        vc = interaction.guild.voice_client
        if vc:
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: check_queue(interaction))
            # Mensaje opcional en consola para saber que funciona
            print(f"Siguiente canción: {titulo}")

# --- COMANDO !help ---
@bot.command(name="help")
async def help_command(ctx):
    help_text = (
        "**🎸 COMANDOS DE FLEXUS BOT**\n\n"
        "**Comandos de Barra (/)**\n"
        "`/play` - Reproduce música a 320kbps\n"
        "`/pause` - Pausa el audio\n"
        "`/resume` - Sigue tocando\n"
        "`/skip` - Salta a la siguiente\n"
        "`/stop` - Limpia todo y sale\n"
        "`/queue` - Mira la lista de espera\n"
        "`/volume` - Ajusta el volumen\n\n"
        "**Comandos de Playlist**\n"
        "`/playlist_create [nombre]` - Crea tu lista personal\n"
        "`/playlist_add [nombre] [cancion]` - Guarda una canción\n"
        "`/playlist_play [nombre]` - ¡Hazla sonar!\n\n"
        "**Otros**\n"
        "`!help` - Muestra este mensaje"
    )
    await ctx.send(help_text)

# --- TUS 10 COMANDOS ORIGINALES (CON EL ARREGLO DE COLA) ---

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
            # Añadimos el 'after' para que llame a la cola cuando termine
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: check_queue(interaction))
            await interaction.followup.send(f"🎶 Reproduciendo a 320kbps: **{titulo}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Música pausada.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Música reanudada.")

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        vc.stop() # Al detenerse, el 'after' del play activará check_queue
        await interaction.response.send_message("⏭️ Siguiente canción.")

@bot.tree.command(name="stop", description="Limpia la cola y saca al bot")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Bot desconectado.")

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
        vc.source = discord.PCMVolumeTransformer(vc.source)
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen al {nivel}%")

@bot.tree.command(name="now", description="Estado actual")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔎 Sonando en HD.")

@bot.tree.command(name="clear", description="Vacía la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada.")

@bot.tree.command(name="reconnect", description="Reinicia conexión")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("🔄 Reiniciado.")

# --- COMANDOS DE PLAYLIST (EL OTRO ARREGLO) ---

@bot.tree.command(name="playlist_create", description="Crea una playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Playlist **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Guarda canción en tu playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message("❌ Crea la playlist primero.")
    
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}** en **{nombre_playlist}**")

@bot.tree.command(name="playlist_play", description="Toca tu playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Playlist vacía.")
    
    # Metemos toda la playlist a la cola
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"💿 Cargando playlist **{nombre}**...")
    
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        check_queue(interaction)

@bot.tree.command(name="sync_all", description="Sincroniza comandos")
async def sync_all(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("✅ Sincronizado.")

bot.run(TOKEN)
