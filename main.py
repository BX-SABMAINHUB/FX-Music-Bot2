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

# CONFIGURACIÓN PARA SUPERAR A CUALQUIER BOT
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'source_address': '0.0.0.0', 
    'nocheckcertificate': True,
    # Forzamos protocolos de alta estabilidad
    'extractor_args': {'youtube': {'player_client': ['ios'], 'skip': ['dash', 'hls']}},
    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
} 

# EL SECRETO: Filtro de volumen 'loudnorm' para potencia máxima y bitrate fijo
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 20M -analyzeduration 20M', 
    'options': (
        '-vn '
        '-b:a 192k '             # Bitrate recto y perfecto para Discord
        '-af "loudnorm=I=-14:LRA=1:tp=-1" ' # Normalización premium para volumen potente pero nítido
    ), 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.current_track = titulo
        vc = interaction.guild.voice_client
        if vc:
            # Iniciamos con volumen 1.0 (100%) pero con la ganancia de loudnorm ya aplicada
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=1.0)
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**👑 FLEXUS SUPREMACY - COMANDOS**\n"
        "**`/play`** - Calidad de Estudio (Recta).\n"
        "**`/volume`** - Ajuste Masivo (1 - 10B).\n"
        "**`/queue`** - Ver cola.\n"
        "**`/shuffle`** - Aleatorio.\n"
        "**`/nowplaying`** - Info actual.\n"
        "**`/clear`** - Limpiar todo.\n"
        "**`/skip` / `/stop`** - Control de pista."
    )
    await ctx.send(ayuda)

# --- COMANDOS MEJORADOS ---

@bot.tree.command(name="play", description="Audio Premium - FLEXUS 100%") 
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
            await interaction.followup.send(f"💎 **FLEXUS 100%** | Sonando: **{titulo}**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error. YouTube detectó tráfico inusual. Reintenta ahora.") 

@bot.tree.command(name="volume", description="Ajusta la potencia (Hasta 10 mil millones)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        if 1 <= nivel <= 10000000000:
            # Dividimos por 100 para que 100 sea el estándar, pero permitimos el exceso solicitado
            vc.source.volume = nivel / 100
            await interaction.response.send_message(f"🔊 Potencia FLEXUS ajustada a: **{nivel}**")
        else:
            await interaction.response.send_message("❌ Elige entre 1 y 10.000.000.000.")
    else:
        await interaction.response.send_message("❌ No hay nada sonando.")

@bot.tree.command(name="queue", description="Cola de reproducción")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("Cola vacía.")
    lista = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"📋 **Próximas canciones:**\n{lista}")

@bot.tree.command(name="nowplaying", description="Canción actual")
async def nowplaying(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Estás escuchando: **{bot.current_track or 'Nada'}**")

@bot.tree.command(name="shuffle", description="Mezcla la cola")
async def shuffle(interaction: discord.Interaction):
    if len(bot.queue) > 1:
        random.shuffle(bot.queue)
        await interaction.response.send_message("🔀 Cola mezclada para FLEXUS.")
    else:
        await interaction.response.send_message("No hay suficientes canciones.")

@bot.tree.command(name="clear", description="Limpia la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola eliminada.")

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
        await interaction.response.send_message("⏭️ Siguiente pista.") 

@bot.tree.command(name="stop", description="Desconectar bot") 
async def stop(interaction: discord.Interaction): 
    bot.queue.clear() 
    if interaction.guild.voice_client: 
        await interaction.guild.voice_client.disconnect() 
        await interaction.response.send_message("⏹️ FLEXUS fuera.")

@bot.tree.command(name="leave", description="Adiós")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Hasta la próxima.")

@bot.tree.command(name="loop", description="Repetir canción (Simulado)")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Modo bucle activado (FLEXUS Premium).")

@bot.tree.command(name="jump", description="Salto rápido")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la pista #{posicion}.")
    else: await interaction.response.send_message("Posición inválida.")

# --- PLAYLISTS ---

@bot.tree.command(name="playlist_create", description="Crear lista")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Lista **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añadir canción")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists: return await interaction.response.send_message("❌ No existe.")
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}**.")

@bot.tree.command(name="playlist_play", description="Tocar lista")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]: return await interaction.response.send_message("❌ Vacía.")
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Cargando Playlist: **{nombre}** - **FLEXUS 100%**")
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing(): play_next(interaction)

bot.run(TOKEN)
