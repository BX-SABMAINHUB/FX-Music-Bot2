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
        # Mantenemos la eliminación del help por defecto para evitar crasheos
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.playlists = {} 

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V2 conectado como {self.user}") 

bot = FlexusBot() 

# CONFIGURACIÓN DE AUDIO OPTIMIZADA (CALIDAD MÁXIMA)
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'source_address': '0.0.0.0', 
    'nocheckcertificate': True,
    # User agent para evitar bloqueos de YouTube
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'postprocessors': [{ 
        'key': 'FFmpegExtractAudio', 
        'preferredcodec': 'opus', 
        'preferredquality': '320', 
    }], 
} 

# Filtros reforzados para mantener la calidad y estabilidad durante toda la canción
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
    'options': '-vn -b:a 320k -vol 256', # -vol 256 es el estándar base limpio
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        vc = interaction.guild.voice_client
        if vc:
            # Aplicamos el transformador de volumen para mantener la consistencia
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        print("Cola finalizada.")

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**🎸 GUÍA DE COMANDOS FLEXUS**\n"
        "**`/play`** - Música en Alta Fidelidad (320kbps).\n"
        "**`/pause` / `/resume`** - Control de reproducción.\n"
        "**`/skip`** - Salta a la siguiente pista.\n"
        "**`/volume`** - Ajuste masivo (Hasta 10.000 Millones).\n"
        "**`/playlist_create`** - Gestiona tus listas.\n"
        "**`/playlist_add`** - Guarda tus temas favoritos.\n"
        "**`/playlist_play`** - Reproduce tus listas.\n"
        "**`!help`** - Muestra este panel."
    )
    await ctx.send(ayuda)

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
            await interaction.followup.send(f"✅ En cola: **{titulo}**") 
        else:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction)) 
            # Mensaje personalizado como pediste
            await interaction.followup.send(f"🎶 Sonando: **{titulo}** - **FLEXUS 100%**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error de conexión con YouTube. Reintenta en unos segundos.") 

@bot.tree.command(name="pause", description="Pausa la música") 
async def pause(interaction: discord.Interaction): 
    vc = interaction.guild.voice_client 
    if vc and vc.is_playing(): 
        vc.pause() 
        await interaction.response.send_message("⏸️ Reproducción pausada.") 
    else: 
        await interaction.response.send_message("❌ No hay audio activo.") 

@bot.tree.command(name="resume", description="Reanuda la música") 
async def resume(interaction: discord.Interaction): 
    vc = interaction.guild.voice_client 
    if vc and vc.is_paused(): 
        vc.resume() 
        await interaction.response.send_message("▶️ Reproducción reanudada.") 

@bot.tree.command(name="skip", description="Salta la canción") 
async def skip(interaction: discord.Interaction): 
    vc = interaction.guild.voice_client 
    if vc: 
        vc.stop() 
        await interaction.response.send_message("⏭️ Canción saltada.") 

@bot.tree.command(name="stop", description="Limpia y sale") 
async def stop(interaction: discord.Interaction): 
    bot.queue.clear() 
    if interaction.guild.voice_client: 
        await interaction.guild.voice_client.disconnect() 
        await interaction.response.send_message("⏹️ Desconectado y cola vaciada.") 

@bot.tree.command(name="volume", description="Ajusta el volumen (Rango masivo)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        # Rango masivo hasta 10.000.000.000
        if 1 <= nivel <= 10000000000:
            vc.source.volume = nivel / 100
            await interaction.response.send_message(f"🔊 Volumen FLEXUS ajustado a: **{nivel}**")
        else:
            await interaction.response.send_message("❌ Elige un valor entre 1 y 10.000.000.000.")
    else:
        await interaction.response.send_message("❌ Debes estar reproduciendo música para ajustar el volumen.")

@bot.tree.command(name="playlist_create", description="Crea una playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Playlist **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añade canción a playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message("❌ La playlist indicada no existe.")
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}** en **{nombre_playlist}**.")

@bot.tree.command(name="playlist_play", description="Toca tu playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ La playlist está vacía o no existe.")
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Cargando playlist: **{nombre}** - **FLEXUS 100%**")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        play_next(interaction)

bot.run(TOKEN)
