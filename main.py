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
        # El comando !help usará este prefijo
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.queue = [] 
        self.playlists = {} 
        self.current_interaction = None

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS V2 (Perfecto) conectado")

bot = FlexusBot()

# CONFIGURACIÓN DE CALIDAD (Mantenida según tu petición)
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

# --- FUNCIÓN CRÍTICA: REPRODUCIR SIGUIENTE (Arregla el silencio) ---
def play_next(guild_id):
    if len(bot.queue) > 0:
        vc = discord.utils.get(bot.voice_clients, guild=bot.get_guild(guild_id))
        if vc:
            url, titulo = bot.queue.pop(0)
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next(guild_id))
            # Envía aviso al canal si tenemos la referencia
            if bot.current_interaction:
                asyncio.run_coroutine_threadsafe(
                    bot.current_interaction.channel.send(f"⏭️ Siguiente en la cola: **{titulo}**"), 
                    bot.loop
                )

# --- COMANDOS ARREGLADOS ---

@bot.tree.command(name="play", description="Reproduce música a máxima calidad")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    bot.current_interaction = interaction
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
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction.guild.id))
            await interaction.followup.send(f"🎶 Reproduciendo: **{titulo}**")
    except Exception as e:
        await interaction.followup.send("❌ Error al cargar. YouTube podría estar saturado.")

@bot.tree.command(name="playlist_create", description="Crea una playlist")
async def playlist_create(interaction: discord.Interaction, nombre: str):
    bot.playlists[nombre] = []
    await interaction.response.send_message(f"🆕 Playlist **{nombre}** creada.")

@bot.tree.command(name="playlist_add", description="Guarda una canción en tu playlist")
async def playlist_add(interaction: discord.Interaction, nombre_playlist: str, busqueda: str):
    await interaction.response.defer()
    if nombre_playlist not in bot.playlists:
        return await interaction.followup.send("❌ Esa playlist no existe.")
    
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    
    bot.playlists[nombre_playlist].append((data['url'], data['title']))
    await interaction.followup.send(f"➕ **{data['title']}** guardada en **{nombre_playlist}**.")

@bot.tree.command(name="playlist_play", description="Reproduce tu playlist guardada")
async def playlist_play(interaction: discord.Interaction, nombre: str):
    if nombre not in bot.playlists or not bot.playlists[nombre]:
        return await interaction.response.send_message("❌ Playlist vacía.")
    
    bot.queue.extend(bot.playlists[nombre])
    await interaction.response.send_message(f"🚀 Cargando playlist **{nombre}**...")
    
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if not vc.is_playing():
        url, titulo = bot.queue.pop(0)
        vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction.guild.id))

# --- RESTO DE COMANDOS DE CONTROL ---

@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause(); await interaction.response.send_message("⏸️")

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume(); await interaction.response.send_message("▶️")

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.stop(); await interaction.response.send_message("⏭️")

@bot.tree.command(name="stop")
async def stop(interaction: discord.Interaction):
    bot.queue.clear(); await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("⏹️")

@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    msg = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue)]) or "Vacía"
    await interaction.response.send_message(f"📋 **Cola:**\n{msg}")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, nivel: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source = discord.PCMVolumeTransformer(interaction.guild.voice_client.source)
        interaction.guild.voice_client.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 {nivel}%")

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue); await interaction.response.send_message("🔀 Mezclada")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear(); await interaction.response.send_message("🗑️")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect(); await interaction.response.send_message("👋")

# --- EL ÚNICO COMANDO CON ! (AYUDA) ---

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="📖 Guía de Comandos FLEXUS", color=discord.Color.blue())
    embed.add_field(name="🎵 Música Básica", value="`/play`: Escuchar canción\n`/pause`: Pausar\n`/resume`: Seguir\n`/skip`: Siguiente\n`/stop`: Parar y limpiar", inline=False)
    embed.add_field(name="📂 Playlists", value="`/playlist_create`: Crear lista\n`/playlist_add`: Guardar canción\n`/playlist_play`: Escuchar tu lista", inline=False)
    embed.add_field(name="⚙️ Ajustes", value="`/volume`: 1-100\n`/queue`: Ver lista\n`/shuffle`: Aleatorio\n`/clear`: Vaciar cola\n`/leave`: Sacar bot", inline=False)
    embed.set_footer(text="Usa / para ver todos los comandos de barra")
    await ctx.send(embed=embed)

bot.run(TOKEN)
