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
        # SOLUCIÓN AL CRASH: Eliminamos el comando help por defecto
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.playlists = {} 

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V2 conectado como {self.user}") 

bot = FlexusBot() 

# CONFIGURACIÓN DE AUDIO (MANTENIENDO TU CALIDAD)
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'source_address': '0.0.0.0', 
    # Intento de evitar el error "Confirm you are not a bot"
    'nocheckcertificate': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        vc = interaction.guild.voice_client
        if vc:
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
    else:
        print("Cola finalizada.")

# --- COMANDO !help (YA NO CRASHEARÁ) ---
@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**🎸 GUÍA DE COMANDOS FLEXUS**\n"
        "**`/play`** - Música a 320kbps.\n"
        "**`/pause` / `/resume`** - Control de audio.\n"
        "**`/skip`** - Salta a la siguiente.\n"
        "**`/volume`** - Ajusta el volumen (1 a 100,000).\n"
        "**`/playlist_create`** - Crea tu lista.\n"
        "**`/playlist_add`** - Guarda canciones.\n"
        "**`/playlist_play`** - Toca tu lista.\n"
        "**`!help`** - Ver este menú."
    )
    await ctx.send(ayuda)

# --- COMANDOS SLASH (MANTENIENDO TU ESTRUCTURA) ---

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
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction)) 
            await interaction.followup.send(f"🎶 Sonando: **{titulo}**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error de YouTube (Bot detectado). Reintenta en un momento.") 

@bot.tree.command(name="pause", description="Pausa la música") 
async def pause(interaction: discord.Interaction): 
    vc = interaction.guild.voice_client 
    if vc and vc.is_playing(): 
        vc.pause() 
        await interaction.response.send_message("⏸️ Pausada.") 
    else: 
        await interaction.response.send_message("❌ No hay nada sonando.") 

@bot.tree.command(name="resume", description="Reanuda la música") 
async def resume(interaction: discord.Interaction): 
    vc = interaction.guild.voice_client 
    if vc and vc.is_paused(): 
        vc.resume() 
        await interaction.response.send_message("▶️ Reanudada.") 

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

# --- COMANDO DE VOLUMEN AÑADIDO ---
@bot.tree.command(name="volume", description="Ajusta el volumen de 1 a 100,000")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        # Limitamos el rango según tu petición
        if 1 <= nivel <= 100000:
            # Discord usa una escala donde 1.0 es 100%, así que dividimos por 100
            vc.source = discord.PCMVolumeTransformer(vc.source)
            vc.source.volume = nivel / 100
            await interaction.response.send_message(f"🔊 Volumen ajustado a: **{nivel}**")
        else:
            await interaction.response.send_message("❌ Por favor elige un número entre 1 y 100,000.")
    else:
        await interaction.response.send_message("❌ No hay música sonando para ajustar el volumen.")

@bot.tree.command(name="playlist_create", description="Crea una playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Playlist **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añade canción a playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message("❌ Esa playlist no existe.")
    
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}** en **{nombre_playlist}**.")

@bot.tree.command(name="playlist_play", description="Toca tu playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Playlist vacía o inexistente.")
    
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Iniciando playlist: **{nombre}**")
    
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        play_next(interaction)

bot.run(TOKEN)
