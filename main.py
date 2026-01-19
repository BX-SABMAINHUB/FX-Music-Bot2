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
        # Help desactivado para evitar conflictos
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.playlists = {} 

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS (Core Stable) conectado como {self.user}") 

bot = FlexusBot() 

# --- CONFIGURACIÓN "ANTI-THROTTLE" (EL SECRETO DE LA ESTABILIDAD) ---
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    # Usamos 'ios' porque YouTube no estrangula tanto la velocidad en móviles Apple
    'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
    'nocheckcertificate': True,
    'source_address': '0.0.0.0', 
    'postprocessors': [{ 
        'key': 'FFmpegExtractAudio', 
        'preferredcodec': 'opus', 
        'preferredquality': '192', # 192k es el límite real de Discord. Poner más es desperdicio que causa lag.
    }], 
} 

# FFmpeg con BÚFER GIGANTE para que si internet baja, la música siga sonando bien
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 10M -analyzeduration 10M', 
    'options': '-vn -b:a 192k', # Bitrate constante y sólido
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        vc = interaction.guild.voice_client
        if vc:
            # Transformador de volumen activado siempre
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        print("Cola finalizada.")

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**💎 COMANDOS FLEXUS (Calidad Estable)**\n"
        "**`/play`** - Sonido de estudio.\n"
        "**`/volume`** - Ajuste hasta 10 mil millones.\n"
        "**`/skip`** - Siguiente canción.\n"
        "**`/pause` / `/resume`** - Control.\n"
        "**`/playlist_create`** - Crear lista.\n"
        "**`/playlist_add`** - Guardar canción.\n"
        "**`/playlist_play`** - Cargar lista.\n"
        "**`/stop`** - Desconectar."
    )
    await ctx.send(ayuda)

@bot.tree.command(name="play", description="Reproduce música (Estabilidad Lara)") 
async def play(interaction: discord.Interaction, busqueda: str): 
    await interaction.response.defer() 
    try: 
        loop = asyncio.get_event_loop() 
        # Descarga sin bloqueo
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
            await interaction.followup.send(f"💎 Sonando: **{titulo}** - **FLEXUS 100%**") 
    except Exception as e: 
        print(f"Error: {e}")
        await interaction.followup.send("❌ Error de red. Intenta de nuevo.") 

@bot.tree.command(name="volume", description="Ajusta el volumen (Infinito)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        if 1 <= nivel <= 10000000000:
            vc.source.volume = nivel / 100
            await interaction.response.send_message(f"🔊 Volumen: **{nivel}**")
        else:
            await interaction.response.send_message("❌ Rango: 1 a 10.000.000.000")
    else:
        await interaction.response.send_message("❌ No hay música sonando.")

@bot.tree.command(name="pause", description="Pausa") 
async def pause(interaction: discord.Interaction): 
    if interaction.guild.voice_client: 
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("⏸️")

@bot.tree.command(name="resume", description="Reanudar") 
async def resume(interaction: discord.Interaction): 
    if interaction.guild.voice_client: 
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("▶️")

@bot.tree.command(name="skip", description="Siguiente") 
async def skip(interaction: discord.Interaction): 
    if interaction.guild.voice_client: 
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️")

@bot.tree.command(name="stop", description="Desconectar") 
async def stop(interaction: discord.Interaction): 
    bot.queue.clear() 
    if interaction.guild.voice_client: 
        await interaction.guild.voice_client.disconnect() 
        await interaction.response.send_message("⏹️") 

@bot.tree.command(name="playlist_create", description="Nueva playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Lista **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añadir a playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message("❌ No existe esa lista.")
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}**")

@bot.tree.command(name="playlist_play", description="Tocar playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Lista vacía.")
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Cargando **{nombre}**...")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        play_next(interaction)

bot.run(TOKEN)
