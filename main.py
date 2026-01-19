import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
import random

TOKEN = os.getenv("DISCORD_TOKEN")

# Configuración de Cliente para evitar bloqueos
class FlexusBot(commands.Bot):
    def __init__(self):
        # Intents necesarios
        intents = discord.Intents.default()
        intents.message_content = True 
        super().__init__(command_prefix="!", intents=intents)
        self.queue = []
        self.playlists = {}

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS SISTEMA ACTIVO - Esperando órdenes.")

bot = FlexusBot()

# --- CONFIGURACIÓN DE AUDIO BLINDADA ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'nocheckcertificate': True, # Vital para evitar errores SSL en servidores
    'ignoreerrors': True,       # Evita que el bot crashee si un video falla
    'no_warnings': True,
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

# --- SISTEMA DE COLA AUTOMÁTICA (CON PROTECCIÓN ANTI-CRASH) ---
def tocar_siguiente(vc):
    if len(bot.queue) > 0:
        try:
            url, title = bot.queue.pop(0)
            print(f"Reproduciendo siguiente: {title}")
            
            # Verificamos si seguimos conectados antes de tocar
            if vc.is_connected():
                vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), 
                        after=lambda e: tocar_siguiente(vc))
            else:
                print("Bot desconectado, limpiando cola.")
                bot.queue.clear()
        except Exception as e:
            print(f"Error al reproducir siguiente canción: {e}")
            tocar_siguiente(vc) # Si falla, intenta la siguiente
    else:
        print("Cola finalizada.")

# --- COMANDO DE AYUDA (Prefijo !) ---
@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="🎛️ Panel de Control FLEXUS", description="Lista de comandos disponibles", color=0x00ff00)
    embed.add_field(name="🎵 Música", value="`/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/now`", inline=False)
    embed.add_field(name="📋 Cola", value="`/queue` (ver), `/clear` (borrar), `/remove` (quitar una), `/jump` (saltar a)", inline=False)
    embed.add_field(name="💾 Playlists", value="`/playlist_create`, `/playlist_add`, `/playlist_play`", inline=False)
    embed.add_field(name="🔊 Ajustes", value="`/volume [1-100]`, `/reconnect` (si falla), `/leave`", inline=False)
    embed.set_footer(text="Usa !help para ver esto de nuevo.")
    await ctx.send(embed=embed)

# --- COMANDOS PRINCIPALES ---

@bot.tree.command(name="play", description="Reproduce música (Calidad 320k)")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    try:
        loop = asyncio.get_event_loop()
        # Usamos run_in_executor para no bloquear el bot mientras busca
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        
        if data is None: 
            return await interaction.followup.send("❌ No se encontró la canción o hubo un error.")
            
        if 'entries' in data: data = data['entries'][0]
        
        url, titulo = data['url'], data['title']
        
        # Conexión segura al canal de voz
        if interaction.user.voice:
            vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        else:
            return await interaction.followup.send("⚠️ ¡Debes estar en un canal de voz!")

        if vc.is_playing():
            bot.queue.append((url, titulo))
            await interaction.followup.send(f"✅ En cola: **{titulo}**")
        else:
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: tocar_siguiente(vc))
            await interaction.followup.send(f"🎶 Sonando: **{titulo}**")
            
    except Exception as e:
        print(f"Error critico en Play: {e}")
        await interaction.followup.send("❌ Error de conexión con YouTube. Prueba `/reconnect`.")

@bot.tree.command(name="playlist_create", description="Crea una playlist personal")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"📂 Playlist **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Guarda una canción en tu playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    if nombre_playlist not in bot.playlists:
        return await interaction.response.send_message(f"❌ La playlist '{nombre_playlist}' no existe.")
    
    await interaction.response.defer()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        if 'entries' in data: data = data['entries'][0]
        bot.playlists[nombre_playlist].append((data['url'], data['title']))
        await interaction.followup.send(f"💾 **{data['title']}** guardada en **{nombre_playlist}**.")
    except:
        await interaction.followup.send("❌ Error al buscar la canción.")

@bot.tree.command(name="playlist_play", description="Reproduce tu playlist guardada")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Playlist vacía o no existe.")
    
    # Añadimos a la cola
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"💿 Cargando **{nombre}**...")
    
    # Si no suena nada, arrancamos
    if interaction.user.voice:
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        if not vc.is_playing():
            tocar_siguiente(vc)
    else:
        await interaction.followup.send("⚠️ Entra a un canal de voz primero.")

# --- RESTO DE COMANDOS DE CONTROL ---

@bot.tree.command(name="skip", description="Siguiente canción")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop() # Esto activa tocar_siguiente automáticamente
        await interaction.response.send_message("⏭️")
    else:
        await interaction.response.send_message("❌ No hay música sonando.")

@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause(); await interaction.response.send_message("⏸️")

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume(); await interaction.response.send_message("▶️")

@bot.tree.command(name="stop")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("⏹️ Desconectado")

@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("Cola vacía.")
    msg = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)])
    await interaction.response.send_message(f"📋 **Cola:**\n{msg[:1900]}") # Limite caracteres Discord

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, nivel: int):
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source = discord.PCMVolumeTransformer(vc.source)
        vc.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 {nivel}%")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear(); await interaction.response.send_message("🗑️ Cola limpia")

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue); await interaction.response.send_message("🔀 Cola mezclada")

@bot.tree.command(name="now")
async def now(interaction: discord.Interaction):
    await interaction.response.send_message("🎵 Revisa el estado de voz.")

@bot.tree.command(name="remove")
async def remove(interaction: discord.Interaction, numero: int):
    if 0 < numero <= len(bot.queue):
        removed = bot.queue.pop(numero-1)
        await interaction.response.send_message(f"🗑️ Borrada: {removed[1]}")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, numero: int):
    if 0 < numero <= len(bot.queue):
        for _ in range(numero-1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"✈️ Saltando a posición {numero}")

@bot.tree.command(name="reconnect")
async def reconnect(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    if interaction.user.voice: await interaction.user.voice.channel.connect()
    await interaction.response.send_message("🔄 Audio reiniciado.")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("👋")

@bot.tree.command(name="sync_all")
async def sync_all(interaction: discord.Interaction):
    await bot.tree.sync()
    await interaction.response.send_message("✅ Comandos sincronizados.")

bot.run(TOKEN)
