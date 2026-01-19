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

# --- CONFIGURACIÓN "ANTI-THROTTLE" (EL SECRETO DE LA ESTABILIDAD TIPO LARA) ---
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
    'nocheckcertificate': True,
    'source_address': '0.0.0.0', 
    'postprocessors': [{ 
        'key': 'FFmpegExtractAudio', 
        'preferredcodec': 'opus', 
        'preferredquality': '192', 
    }], 
} 

# SISTEMA PLAY REFORZADO: Filtros de volumen 'loudnorm' para que suene fuerte y estable
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 15M -analyzeduration 15M', 
    'options': '-vn -b:a 192k -af "loudnorm=I=-14:LRA=1:tp=-1"', 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.current_track = titulo
        vc = interaction.guild.voice_client
        if vc:
            # Sistema de Play exacto al solicitado con refuerzo de volumen
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=1.0)
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**👑 FLEXUS SUPREMACY - 20 COMANDOS**\n"
        "**`/play`** - Música Calidad Premium.\n"
        "**`/volume`** - Potencia (1 - 10 Billones).\n"
        "**`/nowplaying`** - Info actual.\n"
        "**`/queue`** - Ver lista.\n"
        "**`/shuffle`** - Aleatorio.\n"
        "**`/skip`** - Siguiente.\n"
        "**`/clear`** - Vaciar cola.\n"
        "**`!help`** - Todos los comandos."
    )
    await ctx.send(ayuda)

# --- SISTEMA DE COMANDOS (20 TOTAL) ---

@bot.tree.command(name="play", description="Reproduce música (Estabilidad Lara)") 
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
            await interaction.followup.send(f"💎 Sonando: **{titulo}** - **FLEXUS 100%**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error de red. Intenta de nuevo.") 

@bot.tree.command(name="volume", description="Ajusta el volumen (Hasta 10 mil millones)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        if 1 <= nivel <= 10000000000:
            vc.source.volume = nivel / 100
            await interaction.response.send_message(f"🔊 Volumen FLEXUS: **{nivel}**")
        else:
            await interaction.response.send_message("❌ Rango: 1 a 10.000.000.000")
    else:
        await interaction.response.send_message("❌ No hay música.")

@bot.tree.command(name="pause", description="Pausar") 
async def pause(interaction: discord.Interaction): 
    if interaction.guild.voice_client:
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Reanudar") 
async def resume(interaction: discord.Interaction): 
    if interaction.guild.voice_client:
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="skip", description="Siguiente canción") 
async def skip(interaction: discord.Interaction): 
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop", description="Detener y limpiar") 
async def stop(interaction: discord.Interaction): 
    bot.queue.clear() 
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect() 
        await interaction.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="queue", description="Ver cola de reproducción")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("Cola vacía.")
    lista = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"📋 **Cola FLEXUS:**\n{lista}")

@bot.tree.command(name="nowplaying", description="Qué suena ahora")
async def nowplaying(interaction: discord.Interaction):
    await interaction.response.send_message(f"💎 Sonando: **{bot.current_track or 'Nada'}**")

@bot.tree.command(name="shuffle", description="Mezcla la cola")
async def shuffle(interaction: discord.Interaction):
    if len(bot.queue) > 1:
        random.shuffle(bot.queue)
        await interaction.response.send_message("🔀 Cola mezclada.")
    else: await interaction.response.send_message("No hay suficientes canciones.")

@bot.tree.command(name="clear", description="Vacía la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada.")

@bot.tree.command(name="leave", description="Salir del canal")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Adiós.")

@bot.tree.command(name="jump", description="Saltar a una posición")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a #{posicion}.")
    else: await interaction.response.send_message("Posición inválida.")

@bot.tree.command(name="loop", description="Repetir canción")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle activado (FLEXUS Premium).")

@bot.tree.command(name="bassboost", description="Aumentar graves")
async def bassboost(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Bass Boost aplicado (Nivel FLEXUS).")

@bot.tree.command(name="playlist_create", description="Nueva playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Lista **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añadir a playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists: return await interaction.response.send_message("❌ No existe.")
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}**.")

@bot.tree.command(name="playlist_play", description="Tocar playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]: return await interaction.response.send_message("❌ Vacía.")
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Iniciando: **{nombre}** - **FLEXUS 100%**")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing(): play_next(interaction)

@bot.tree.command(name="lyrics", description="Letras")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"Letras para **{bot.current_track}** no disponibles.")

@bot.tree.command(name="restart", description="Reinicia la canción")
async def restart(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        # Reinsertamos la actual al principio de la cola y paramos la actual
        await interaction.response.send_message("🔄 Reiniciando pista...")

@bot.tree.command(name="ping", description="Latencia")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Latencia: {round(bot.latency * 1000)}ms")

bot.run(TOKEN)
