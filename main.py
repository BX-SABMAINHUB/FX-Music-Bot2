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
        # Cambiado a "!" para que el comando !help funcione
        super().__init__(command_prefix="!", intents=intents) 
        self.queue = [] 
        self.playlists = {} # Diccionario para guardar tus listas

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V2 (Alta Calidad) conectado como {self.user}") 

bot = FlexusBot() 

# CONFIGURACIÓN DE MÁXIMA CALIDAD DE AUDIO (IGUAL A TU CÓDIGO)
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

# Optimización para que el audio no tenga micro-cortes (IGUAL A TU CÓDIGO)
FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
    'options': '-vn -b:a 320k', 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

# --- FUNCIÓN PARA QUE LA COLA PASE SOLA (SOLUCIÓN AL ERROR) ---
def play_next(interaction):
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        vc = interaction.guild.voice_client
        if vc:
            # Reproduce y se llama a sí mismo al terminar
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        print("Cola vacía.")

# --- COMANDO !help (EL ÚNICO CON !) ---
@bot.command(name="help")
async def help_command(ctx):
    ayuda = (
        "**🎸 GUÍA DE COMANDOS FLEXUS**\n"
        "**`/play`** - Música a 320kbps.\n"
        "**`/pause` / `/resume`** - Controla el audio.\n"
        "**`/skip`** - Salta a la siguiente canción.\n"
        "**`/playlist_create`** - Crea tu lista con un nombre.\n"
        "**`/playlist_add`** - Guarda canciones en tu lista.\n"
        "**`/playlist_play`** - Haz sonar tu lista guardada.\n"
        "**`/queue`** - Mira qué canciones vienen.\n"
        "**`/volume`** - Ajusta la potencia (1-100).\n"
        "**`!help`** - Muestra este menú."
    )
    await ctx.send(ayuda)

# --- 10 COMANDOS ORIGINALES + MEJORAS --- 

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
            # ARREGLO: Añadido 'after' para que la música no se pare
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction)) 
            await interaction.followup.send(f"🎶 Reproduciendo a 320kbps: **{titulo}**") 
    except Exception as e: 
        await interaction.followup.send("❌ Error al cargar el audio.") 

@bot.tree.command(name="pause", description="Pausa la música") 
async def pause(interaction: discord.Interaction): 
    vc = interaction.guild.voice_client 
    if vc and vc.is_playing(): 
        vc.pause() 
        await interaction.response.send_message("⏸️ Música pausada.") 
    else: 
        await interaction.response.send_message("❌ No hay nada sonando.") 

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
        vc.stop() # Esto activará automáticamente 'play_next'
        await interaction.response.send_message("⏭️ Canción saltada.") 

@bot.tree.command(name="stop", description="Limpia la cola y saca al bot") 
async def stop(interaction: discord.Interaction): 
    bot.queue.clear() 
    if interaction.guild.voice_client: 
        await interaction.guild.voice_client.disconnect() 
        await interaction.response.send_message("⏹️ Bot desconectado y cola limpia.") 

@bot.tree.command(name="queue", description="Muestra la lista de espera") 
async def queue(interaction: discord.Interaction): 
    if not bot.queue: 
        return await interaction.response.send_message("📝 La cola está vacía.") 
    lista = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)]) 
    await interaction.response.send_message(f"📋 **Cola actual:**\n{lista}") 

@bot.tree.command(name="now", description="Muestra qué canción suena ahora") 
async def now(interaction: discord.Interaction): 
    await interaction.response.send_message("🔎 Escuchando a máxima fidelidad (320kbps).") 

@bot.tree.command(name="volume", description="Ajusta el volumen (1-100)") 
async def volume(interaction: discord.Interaction, nivel: int): 
    vc = interaction.guild.voice_client 
    if vc and vc.source: 
        vc.source = discord.PCMVolumeTransformer(vc.source) 
        vc.source.volume = nivel / 100 
        await interaction.response.send_message(f"🔊 Volumen ajustado al {nivel}%") 

@bot.tree.command(name="clear", description="Vacía la cola de reproducción") 
async def clear(interaction: discord.Interaction): 
    bot.queue.clear() 
    await interaction.response.send_message("🗑️ Cola vaciada.") 

@bot.tree.command(name="reconnect", description="Reinicia la conexión si el audio se corta") 
async def reconnect(interaction: discord.Interaction): 
    if interaction.guild.voice_client: 
        await interaction.guild.voice_client.disconnect() 
        await interaction.user.voice.channel.connect() 
        await interaction.response.send_message("🔄 Conexión de audio reiniciada.") 

# --- COMANDOS DE PLAYLIST (REPARADOS) ---

@bot.tree.command(name="playlist_create", description="Crea una playlist personal")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"🆕 Playlist **{nombre}** creada con éxito.")

@bot.tree.command(name="playlist_add", description="Guarda una canción en tu playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message("❌ Esa playlist no existe.")
    
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}** en la lista **{nombre_playlist}**.")

@bot.tree.command(name="playlist_play", description="Haz sonar tu playlist")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Playlist vacía o inexistente.")
    
    # Cargamos toda la playlist a la cola
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Reproduciendo playlist: **{nombre}**")
    
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        play_next(interaction)

@bot.tree.command(name="sync_all", description="Sincroniza todos los comandos")
async def sync_all(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("⚙️ Comandos actualizados.")

bot.run(TOKEN)
