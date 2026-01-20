import discord 
from discord import app_commands 
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random

TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?appName=Cluster0"
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

# CONFIGURACIÓN MAESTRA DE AUDIO (CALIDAD RECTA)
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'source_address': '0.0.0.0', 
    'nocheckcertificate': True,
    'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'postprocessors': [{ 
        'key': 'FFmpegExtractAudio', 
        'preferredcodec': 'opus', 
        'preferredquality': '320', 
    }], 
} 

# Filtro loudnorm = Volumen potente y recto sin altibajos
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 20M -analyzeduration 20M', 
    'options': '-vn -b:a 320k -af "loudnorm=I=-14:LRA=1:tp=-1"', 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.current_track = titulo
        vc = interaction.guild.voice_client
        if vc:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=1.0)
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**👑 COMANDOS FLEXUS 100%**\n"
        "**`/play`** - Calidad de Estudio.\n"
        "**`/volume`** - Hasta 10 Billones.\n"
        "**`/nowplaying`** - Info actual.\n"
        "**`/queue`** - Ver lista.\n"
        "**`/shuffle`** - Aleatorio.\n"
        "**`/skip` / `/stop`** - Control.\n"
        "**`!help`** - Ver todo."
    )
    await ctx.send(ayuda)

# --- SISTEMA DE 20 COMANDOS ---

@bot.tree.command(name="play", description="Música a máxima fidelidad - FLEXUS 100%") 
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
            await interaction.followup.send(f"🎶 Sonando: **{titulo}** - **FLEXUS 100%**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error de YouTube. Reintenta.") 

@bot.tree.command(name="volume", description="Ajusta la potencia (Hasta 10 mil millones)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        if 1 <= nivel <= 10000000000:
            vc.source.volume = nivel / 100
            await interaction.response.send_message(f"🔊 Potencia FLEXUS 100%: **{nivel}**")
        else: await interaction.response.send_message("❌ Rango inválido.")
    else: await interaction.response.send_message("❌ No hay música.")

@bot.tree.command(name="pause", description="Pausa") 
async def pause(interaction: discord.Interaction): 
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️")

@bot.tree.command(name="resume", description="Reanuda") 
async def resume(interaction: discord.Interaction): 
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️")

@bot.tree.command(name="skip", description="Siguiente") 
async def skip(interaction: discord.Interaction): 
    if interaction.guild.voice_client: interaction.guild.voice_client.stop()
    await interaction.response.send_message("⏭️")

@bot.tree.command(name="stop", description="Limpia y sale") 
async def stop(interaction: discord.Interaction): 
    bot.queue.clear() 
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️") 

@bot.tree.command(name="nowplaying", description="Qué suena ahora")
async def nowplaying(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Sonando: **{bot.current_track or 'Nada'}**")

@bot.tree.command(name="queue", description="Ver lista de espera")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("Cola vacía.")
    lista = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"📋 **Próximas:**\n{lista}")

@bot.tree.command(name="shuffle", description="Mezcla la cola")
async def shuffle(interaction: discord.Interaction):
    if len(bot.queue) > 1:
        random.shuffle(bot.queue)
        await interaction.response.send_message("🔀 Mezclado.")
    else: await interaction.response.send_message("Pocas canciones.")

@bot.tree.command(name="clear", description="Vaciar cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Vaciado.")

@bot.tree.command(name="leave", description="Adiós")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋")

@bot.tree.command(name="loop", description="Repetir (Simulado)")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Loop Flexus Activado.")

@bot.tree.command(name="jump", description="Saltar a posición")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la #{posicion}")
    else: await interaction.response.send_message("No existe.")

@bot.tree.command(name="lyrics", description="Letras (Simulado)")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message("🎶 Buscando letras en la red...")

@bot.tree.command(name="ping", description="Latencia del bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Latencia: {round(bot.latency * 1000)}ms")

@bot.tree.command(name="restart", description="Reiniciar canción")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando pista actual...")

@bot.tree.command(name="playlist_create", description="Crea una playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Lista **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añade canción")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists: return await interaction.response.send_message("❌ No existe.")
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}**.")

@bot.tree.command(name="playlist_play", description="Toca la lista")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]: return await interaction.response.send_message("❌ Vacía.")
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Cargando Playlist: **{nombre}**")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing(): play_next(interaction)

@bot.tree.command(name="bassboost", description="Más graves")
async def bassboost(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Bass Boost Flexus Activado.")

bot.run(TOKEN)
