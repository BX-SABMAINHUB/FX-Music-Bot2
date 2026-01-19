import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
import random

TOKEN = os.getenv("DISCORD_TOKEN")

# Configuramos el prefijo '!' para el comando help
class FlexusBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.queue = [] 
        self.playlists = {} # Almacén de playlists

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS FINAL conectado como {self.user}")

bot = FlexusBot()

# --- TU CONFIGURACIÓN DE AUDIO (INTACTA) ---
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

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 320k',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- SISTEMA AUTOMÁTICO DE COLA ---
def tocar_siguiente(vc):
    if len(bot.queue) > 0:
        # Sacamos la siguiente canción
        url, title = bot.queue.pop(0)
        # La reproducimos y volvemos a llamar a esta función cuando acabe
        vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: tocar_siguiente(vc))
        print(f"Reproduciendo automáticamente: {title}")
    else:
        print("Cola terminada.")

# --- COMANDO ÚNICO DE AYUDA CON '!' ---

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="🎸 Guía de Comandos FLEXUS", color=discord.Color.green())
    
    embed.add_field(name="🎵 Música Básica", value="`/play [cancion]`: Poner música\n`/pause`: Pausar\n`/resume`: Reanudar\n`/stop`: Desconectar\n`/skip`: Siguiente canción\n`/volume [1-100]`: Ajustar volumen", inline=False)
    embed.add_field(name="📜 Gestión de Cola", value="`/queue`: Ver lista\n`/clear`: Borrar lista\n`/remove [numero]`: Borrar canción específica\n`/jump [numero]`: Saltar a una canción\n`/shuffle`: Mezclar lista", inline=False)
    embed.add_field(name="💾 Playlists", value="`/playlist_create [nombre]`: Crear lista nueva\n`/playlist_add [nombre] [cancion]`: Guardar canción\n`/playlist_play [nombre]`: Cargar y escuchar lista", inline=False)
    embed.add_field(name="⚙️ Otros", value="`/now`: Canción actual\n`/leave`: Echar al bot\n`/reconnect`: Reiniciar audio\n`!help`: Ver este menú", inline=False)
    
    await ctx.send(embed=embed)


# --- COMANDOS SLASH (BARRA) ---

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
            # AQUÍ ESTÁ LA CORRECCIÓN: Añadimos 'after' para que siga tocando al terminar
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: tocar_siguiente(vc))
            await interaction.followup.send(f"🎶 Reproduciendo a 320kbps: **{titulo}**")
    except Exception as e:
        await interaction.followup.send("❌ Error al cargar el audio.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Música pausada.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Música reanudada.")

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop() # Al parar, el 'after' de play disparará tocar_siguiente()
        await interaction.response.send_message("⏭️ Saltando canción...")

@bot.tree.command(name="stop", description="Limpia la cola y saca al bot")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Bot desconectado.")

@bot.tree.command(name="queue", description="Muestra la lista de espera")
async def queue(interaction: discord.Interaction):
    if not bot.queue:
        return await interaction.response.send_message("📝 La cola está vacía.")
    lista = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)])
    await interaction.response.send_message(f"📋 **Cola actual:**\n{lista}")

@bot.tree.command(name="volume", description="Ajusta el volumen (1-100)")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source = discord.PCMVolumeTransformer(vc.source)
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen ajustado al {nivel}%")

@bot.tree.command(name="clear", description="Vacía la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada.")

@bot.tree.command(name="reconnect", description="Reinicia la conexión de audio")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("🔄 Conexión reiniciada.")

@bot.tree.command(name="now", description="Estado actual")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 El bot está activo.")

# --- COMANDOS DE PLAYLIST Y EXTRAS ---

@bot.tree.command(name="playlist_create", description="Crea una nueva playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"🆕 Playlist **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Añade una canción a una playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message("❌ Playlist no encontrada. Crea una primero.")
    
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"💾 Guardada: **{data['title']}** en **{nombre_playlist}**")

@bot.tree.command(name="playlist_play", description="Reproduce una playlist completa")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Playlist vacía o inexistente.")
    
    # Añadimos las canciones de la playlist a la cola principal
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"💿 Cargando playlist **{nombre}** ({len(bot.playlists[nombre])} canciones)...")
    
    # CORRECCIÓN: Si no hay nada sonando, arrancamos la primera canción manualmente
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        tocar_siguiente(vc)

@bot.tree.command(name="shuffle", description="Mezcla la cola actual")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Cola mezclada.")

@bot.tree.command(name="remove", description="Elimina una canción por su posición")
async def remove(interaction: discord.Interaction, numero: int):
    if 0 < numero <= len(bot.queue):
        eliminada = bot.queue.pop(numero-1)
        await interaction.response.send_message(f"❌ Eliminada: {eliminada[1]}")
    else:
        await interaction.response.send_message("❌ Número inválido.")

@bot.tree.command(name="jump", description="Salta directamente a una posición")
async def jump(interaction: discord.Interaction, numero: int):
    if 0 < numero <= len(bot.queue):
        # Eliminamos las canciones anteriores para llegar a la deseada
        for _ in range(numero - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop() # Esto dispara tocar_siguiente con la nueva primera canción
        await interaction.response.send_message(f"✈️ Saltando a la posición {numero}...")
    else:
        await interaction.response.send_message("❌ Posición inválida.")

@bot.tree.command(name="leave", description="Fuerza al bot a salir")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Adiós.")

@bot.tree.command(name="lyrics", description="Ver letras (En mantenimiento)")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message("📝 Función en desarrollo.")

@bot.tree.command(name="sync_all", description="Sincroniza los comandos")
async def sync_all(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("✅ Comandos sincronizados.")

bot.run(TOKEN)
