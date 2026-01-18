import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os
import logging
import random

# 1. CONFIGURACIÓN DE LOGS (Para ver errores en Railway)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FLEXUS')

# 2. CARGA DEL TOKEN DESDE RAILWAY
TOKEN = os.getenv("DISCORD_TOKEN")

# 3. CONFIGURACIÓN MAESTRA DE AUDIO (YouTube y FFmpeg)
# Estas opciones son las que evitan que el bot se quede mudo
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# 4. CLASE PRINCIPAL DEL BOT
class FlexusBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="fx!", intents=intents)
        self.queues = {} # Diccionario para guardar las listas de canciones de cada servidor

    async def setup_hook(self):
        # Sincroniza los comandos de barra diagonal (Slash Commands)
        await self.tree.sync()
        logger.info(f"--- FLEXUS HA INICIADO SESIÓN COMO {self.user} ---")

bot = FlexusBot()

# 5. MOTOR DE PROCESAMIENTO DE AUDIO
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, query, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

# 6. FUNCIÓN PARA GESTIONAR LA COLA (PLAY NEXT)
def check_queue(interaction, guild_id):
    if guild_id in bot.queues and bot.queues[guild_id]:
        next_song = bot.queues[guild_id].pop(0)
        vc = interaction.guild.voice_client
        if vc:
            vc.play(next_song['source'], after=lambda e: check_queue(interaction, guild_id))
            asyncio.run_coroutine_threadsafe(
                interaction.channel.send(f"⏭️ Siguiente en la lista: **{next_song['title']}**"),
                bot.loop
            )

# 7. COMANDOS DE MÚSICA (SLASH COMMANDS)

@bot.tree.command(name="play", description="Reproduce música de YouTube")
@app_commands.describe(busqueda="Nombre de la canción o artista", url="Link opcional")
async def play(interaction: discord.Interaction, busqueda: str = None, url: str = None):
    # Verificar si el usuario está en un canal de voz
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ ¡Debes estar en un canal de voz!", ephemeral=True)

    await interaction.response.defer() # Da tiempo al bot para procesar (quita el 'pensando')
    
    query = url if url else busqueda
    if not query:
        return await interaction.followup.send("❌ Por favor, escribe el nombre de una canción o pega un link.")

    try:
        # Conectar al canal de voz si no está conectado
        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()

        # Obtener la fuente de audio
        player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
        
        guild_id = interaction.guild.id
        if guild_id not in bot.queues:
            bot.queues[guild_id] = []

        if vc.is_playing():
            bot.queues[guild_id].append({'source': player, 'title': player.title})
            await interaction.followup.send(f"⌛ Añadida a la cola: **{player.title}**")
        else:
            vc.play(player, after=lambda e: check_queue(interaction, guild_id))
            await interaction.followup.send(f"▶️ Sonando ahora: **{player.title}**")

    except Exception as e:
        logger.error(f"Error en comando play: {e}")
        await interaction.followup.send(f"❌ Ocurrió un error al intentar reproducir el audio.")

@bot.tree.command(name="stop", description="Detiene la música y limpia la cola")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        bot.queues[interaction.guild.id] = []
        vc.stop()
        await interaction.response.send_message("⏹️ Música detenida y lista de reproducción vaciada.")
    else:
        await interaction.response.send_message("❌ No estoy reproduciendo nada ahora mismo.")

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop() # Al detenerse, el parámetro 'after' de vc.play activará la siguiente canción
        await interaction.response.send_message("⏭️ Saltando canción...")
    else:
        await interaction.response.send_message("❌ No hay nada que saltar.")

@bot.tree.command(name="leave", description="Saca al bot del canal de voz")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        bot.queues[interaction.guild.id] = []
        await interaction.response.send_message("👋 ¡Nos vemos! Me he desconectado.")
    else:
        await interaction.response.send_message("❌ No estoy en ningún canal de voz.")

@bot.tree.command(name="queue", description="Muestra las canciones en espera")
async def queue(interaction: discord.Interaction):
    q = bot.queues.get(interaction.guild.id, [])
    if not q:
        return await interaction.response.send_message("📁 La cola está vacía.")
    
    lista = "\n".join([f"**{i+1}.** {song['title']}" for i, song in enumerate(q)])
    await interaction.response.send_message(f"📜 **Lista de reproducción:**\n{lista}")

# Comando de emergencia para sincronizar comandos de texto
@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Comandos de barra (/) sincronizados.")

# 8. EJECUCIÓN
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERROR: No se encontró la variable DISCORD_TOKEN en Railway.")
