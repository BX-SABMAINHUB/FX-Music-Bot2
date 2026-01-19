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
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.playlists = {} 

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V2 (SABR Fixed) conectado como {self.user}") 

bot = FlexusBot() 

# CONFIGURACIÓN MAESTRA PARA EVITAR ERRORES DE SABR Y BLOQUEOS
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'source_address': '0.0.0.0', 
    'nocheckcertificate': True,
    # Forzamos un cliente que no use SABR para evitar el error de URL faltante
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'postprocessors': [{ 
        'key': 'FFmpegExtractAudio', 
        'preferredcodec': 'opus', 
        'preferredquality': '320', 
    }], 
} 

# Opciones de FFmpeg optimizadas para que no colapse el flujo de audio
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
    'options': '-vn -b:a 320k', 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        vc = interaction.guild.voice_client
        if vc:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        print("Cola finalizada.")

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**🎸 GUÍA DE COMANDOS FLEXUS**\n"
        "**`/play`** - Música Alta Calidad (SABR Fixed).\n"
        "**`/pause` / `/resume`** - Control total.\n"
        "**`/skip`** - Siguiente canción.\n"
        "**`/volume`** - Hasta 10 mil millones.\n"
        "**`!help`** - Ver comandos."
    )
    await ctx.send(ayuda)

@bot.tree.command(name="play", description="Reproduce música a máxima calidad") 
async def play(interaction: discord.Interaction, busqueda: str): 
    await interaction.response.defer() 
    try: 
        loop = asyncio.get_event_loop()
        # Intentamos extraer info con el parche de cliente
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False)) 
        if 'entries' in data: data = data['entries'][0] 
        
        url, titulo = data['url'], data['title'] 
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect() 

        if vc.is_playing(): 
            bot.queue.append((url, titulo)) 
            await interaction.followup.send(f"✅ En cola: **{titulo}**") 
        else:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction)) 
            await interaction.followup.send(f"🎶 Sonando: **{titulo}** - **FLEXUS 100%**") 
    except Exception as e: 
        print(f"Error detectado: {e}")
        await interaction.followup.send("❌ Error de YouTube. Prueba con el nombre exacto de la canción.") 

@bot.tree.command(name="volume", description="Ajusta el volumen (Rango masivo)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        if 1 <= nivel <= 10000000000:
            vc.source.volume = nivel / 100
            await interaction.response.send_message(f"🔊 Volumen FLEXUS: **{nivel}**")
        else:
            await interaction.response.send_message("❌ Rango: 1 a 10.000.000.000.")
    else:
        await interaction.response.send_message("❌ No hay música sonando.")

@bot.tree.command(name="skip", description="Salta la canción") 
async def skip(interaction: discord.Interaction): 
    vc = interaction.guild.voice_client 
    if vc: 
        vc.stop() 
        await interaction.response.send_message("⏭️ Saltada.") 

@bot.tree.command(name="stop", description="Limpia y sale") 
async def stop(interaction: discord.Interaction): 
    bot.queue.clear() 
    if interaction.guild.voice_client: 
        await interaction.guild.voice_client.disconnect() 
        await interaction.response.send_message("⏹️ Desconectado.")

# --- COMANDOS DE PLAYLIST IGUALES ---
@bot.tree.command(name="playlist_create", description="Crea una playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Playlist **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añade canción a playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message("❌ No existe.")
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}**.")

@bot.tree.command(name="playlist_play", description="Toca tu playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Vacía.")
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Playlist: **{nombre}** - **FLEXUS 100%**")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        play_next(interaction)

bot.run(TOKEN)
