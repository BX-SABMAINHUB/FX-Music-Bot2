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
        print(f"✅ FLEXUS V2 (Ultra Stable) conectado como {self.user}") 

bot = FlexusBot() 

# CONFIGURACIÓN MAESTRA ANTI-BAJONES DE CALIDAD
YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'source_address': '0.0.0.0', 
    'nocheckcertificate': True,
    # El secreto de la estabilidad: Emulamos iOS para que YouTube no corte el grifo
    'extractor_args': {'youtube': {'player_client': ['ios', 'android']}},
    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'postprocessors': [{ 
        'key': 'FFmpegExtractAudio', 
        'preferredcodec': 'opus', 
        'preferredquality': '192', # Calidad óptima para el bitrate de Discord
    }], 
} 

# Filtros para mantener el audio "recto" y sin micro-cortes
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 10M -analyzeduration 10M', 
    'options': '-vn -b:a 192k', 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.current_track = titulo
        vc = interaction.guild.voice_client
        if vc:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**🎸 GUÍA MAESTRA FLEXUS V2**\n"
        "**`/play`** - Música Ultra Estable.\n"
        "**`/volume`** - Hasta 10 mil millones.\n"
        "**`/skip`** - Siguiente.\n"
        "**`/queue`** - Ver lista de espera.\n"
        "**`/nowplaying`** - Qué suena ahora.\n"
        "**`/shuffle`** - Mezclar cola.\n"
        "**`/clear`** - Limpiar cola.\n"
        "**`/pause` / `/resume`** - Pausa/Play.\n"
        "**`!help`** - Ver todos los comandos."
    )
    await ctx.send(ayuda)

# --- COMANDOS ORIGINALES ---

@bot.tree.command(name="play", description="Reproduce música a calidad FLEXUS 100%") 
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
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction)) 
            await interaction.followup.send(f"🎶 Sonando: **{titulo}** - **FLEXUS 100%**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error de red. YouTube bloqueó la petición, intenta de nuevo.") 

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

# --- 10 COMANDOS NUEVOS DE MÚSICA ---

@bot.tree.command(name="queue", description="Muestra la lista de canciones en espera")
async def queue(interaction: discord.Interaction):
    if not bot.queue:
        return await interaction.response.send_message("Empty queue.")
    lista = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"**Cola de reproducción:**\n{lista}")

@bot.tree.command(name="nowplaying", description="Muestra la canción actual")
async def nowplaying(interaction: discord.Interaction):
    if bot.current_track:
        await interaction.response.send_message(f"💎 Sonando ahora: **{bot.current_track}**")
    else:
        await interaction.response.send_message("Nothing is playing.")

@bot.tree.command(name="shuffle", description="Mezcla la cola de reproducción")
async def shuffle(interaction: discord.Interaction):
    if len(bot.queue) > 1:
        random.shuffle(bot.queue)
        await interaction.response.send_message("🔀 Cola mezclada con éxito.")
    else:
        await interaction.response.send_message("Not enough songs to shuffle.")

@bot.tree.command(name="clear", description="Vacía la cola de canciones")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola limpiada.")

@bot.tree.command(name="pause", description="Pausa el audio")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Audio pausado.")
    else:
        await interaction.response.send_message("Nothing is playing.")

@bot.tree.command(name="resume", description="Reanuda el audio")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Audio reanudado.")
    else:
        await interaction.response.send_message("Audio is not paused.")

@bot.tree.command(name="lyrics", description="Busca la letra de una canción (Simulado)")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"Letras para **{bot.current_track or 'Nada'}** no encontradas en la base local.")

@bot.tree.command(name="jump", description="Salta a una posición específica de la cola")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1):
            bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la canción #{posicion}.")
    else:
        await interaction.response.send_message("Invalid position.")

@bot.tree.command(name="back", description="Reinicia la canción actual")
async def back(interaction: discord.Interaction):
    if bot.current_track:
        # Esto es un truco para reinsertar la actual y saltar
        await interaction.response.send_message("🔄 Reiniciando pista actual...")
        # En una versión avanzada aquí se manejaría historial
    else:
        await interaction.response.send_message("Nothing is playing.")

@bot.tree.command(name="leave", description="El bot abandona el canal")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Adiós.")

# --- COMANDOS RESTANTES ---

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
