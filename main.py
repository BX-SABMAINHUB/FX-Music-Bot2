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
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.playlists = {} 
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V2 (God Mode) conectado como {self.user}") 

bot = FlexusBot() 

# CONFIGURACIÓN DE EXTRACCIÓN NIVEL LARA/JOKEY
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'source_address': '0.0.0.0', 
    'nocheckcertificate': True,
    'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'postprocessors': [{ 
        'key': 'FFmpegExtractAudio', 
        'preferredcodec': 'opus', 
        'preferredquality': '256', # Punto dulce para estabilidad en servidores
    }], 
} 

# EL SECRETO: -filter:a "volume=2.0" duplica la potencia base antes de que tú subas el volumen
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 20M -analyzeduration 20M', 
    'options': '-vn -b:a 256k -filter:a "volume=2.5, aresample=48000" -preset veryfast', 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.current_track = titulo
        vc = interaction.guild.voice_client
        if vc:
            # Re-aplicamos el transformador para que el volumen masivo funcione sobre la base ya potenciada
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=1.0)
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**👑 FLEXUS SUPREMACY - EL MEJOR BOT DE MÚSICA**\n"
        "**`/play`** - Audio Hi-Fi Potenciado.\n"
        "**`/volume`** - Ajuste Extremo (Hasta 10 Billones).\n"
        "**`/nowplaying`** - Info de la pista.\n"
        "**`/queue`** - Ver cola.\n"
        "**`/shuffle`** - Aleatorio.\n"
        "**`/clear`** - Limpiar cola.\n"
        "**`/skip`** - Siguiente.\n"
        "**`/pause` / `/resume`** - Control.\n"
        "**`!help`** - Este menú."
    )
    await ctx.send(ayuda)

@bot.tree.command(name="play", description="Reproduce con la máxima potencia de FLEXUS") 
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
            bot.current_track = titulo
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=1.0)
            vc.play(source, after=lambda e: play_next(interaction)) 
            await interaction.followup.send(f"🔥 **FLEXUS 100% (Modo Bestia)**: **{titulo}**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error de red (SABR/YouTube). Reintenta.") 

@bot.tree.command(name="volume", description="Aumenta el volumen a niveles masivos")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        # Ahora el nivel 100 será mucho más fuerte que antes por el filtro de ganancia
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Potencia FLEXUS al: **{nivel}**")
    else:
        await interaction.response.send_message("❌ No hay música sonando.")

# --- COMANDOS ADICIONALES PARA SUPERAR A LA COMPETENCIA ---

@bot.tree.command(name="queue", description="Ver la cola de reproducción")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("Cola vacía.")
    msg = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"📋 **Próximas canciones:**\n{msg}")

@bot.tree.command(name="nowplaying", description="Lo que suena")
async def nowplaying(interaction: discord.Interaction):
    status = f"💎 Sonando: **{bot.current_track}**" if bot.current_track else "Nada."
    await interaction.response.send_message(status)

@bot.tree.command(name="shuffle", description="Mezcla todo")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Mezclado.")

@bot.tree.command(name="clear", description="Limpia la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Limpia.")

@bot.tree.command(name="skip", description="Siguiente canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️")

@bot.tree.command(name="stop", description="Detener todo")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️")

@bot.tree.command(name="playlist_create", description="Nueva playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añade a tu lista")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists: return await interaction.response.send_message("No existe.")
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}**")

@bot.tree.command(name="playlist_play", description="Tocar playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]: return await interaction.response.send_message("Vacía.")
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Cargando lista: **{nombre}**")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing(): play_next(interaction)

bot.run(TOKEN)
