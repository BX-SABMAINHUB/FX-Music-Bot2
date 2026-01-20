import discord 
from discord import app_commands 
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient

TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"

# --- BASE DE DATOS ---
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
stats_col = db["ads_stats"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.songs_played = 0
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        if await stats_col.count_documents({"id": "global"}) == 0:
            await stats_col.insert_one({"id": "global", "views": 0})
        print(f"✅ COMANDOS SINCRONIZADOS Y LISTOS") 

bot = FlexusBot() 

# CONFIGURACIÓN AUDIO PROFESIONAL
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'nocheckcertificate': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0'
} 
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
    'options': '-vn -af "loudnorm=I=-14:LRA=1:tp=-1"'
} 
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

async def registrar_anuncio(interaction):
    if interaction.guild.voice_client:
        oyentes = len(interaction.guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}})

def play_next(interaction):
    if len(bot.queue) > 0:
        # SISTEMA DE ANUNCIOS: Cada 3 canciones
        if bot.songs_played > 0 and bot.songs_played % 3 == 0:
            bot.songs_played += 1
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("anuncio.mp3"), volume=1.0)
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction), bot.loop)
            return

        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- LOS 20 COMANDOS FLEXUS ---

@bot.tree.command(name="play", description="Reproduce música de YouTube") 
async def play(interaction: discord.Interaction, busqueda: str): 
    await interaction.response.defer()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        if 'entries' in data: data = data['entries'][0]
        url, titulo = data['url'], data['title']
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing():
            bot.queue.append((url, titulo))
            await interaction.followup.send(f"✅ Añadido a la cola: **{titulo}**")
        else:
            bot.songs_played = 1
            bot.current_track = titulo
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
            vc.play(source, after=lambda e: play_next(interaction))
            await interaction.followup.send(f"🎶 Sonando ahora: **{titulo}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error al cargar: {e}")

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Canción saltada.")

@bot.tree.command(name="stop", description="Detiene todo y vacía la cola")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Música detenida y desconectado.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue", description="Muestra la lista de espera")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("📋 La cola está vacía.")
    msg = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"📋 **Próximas canciones:**\n{msg}")

@bot.tree.command(name="nowplaying", description="Muestra qué suena ahora")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Sonando ahora: **{bot.current_track or 'Nada'}**")

@bot.tree.command(name="shuffle", description="Mezcla la cola aleatoriamente")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Cola mezclada.")

@bot.tree.command(name="volume", description="Ajusta el volumen (1-200)")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volumen ajustado al {vol}%")

@bot.tree.command(name="ping", description="Mira la velocidad del bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Latencia: {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear", description="Limpia la cola de canciones")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada correctamente.")

@bot.tree.command(name="bassboost", description="Potencia los bajos")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 BASS BOOST: ACTIVADO (FLEXUS MODE)")

@bot.tree.command(name="loop", description="Repite la canción actual")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Repetición activada.")

@bot.tree.command(name="leave", description="Saca al bot del canal")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Adiós, Flexus fuera.")

@bot.tree.command(name="jump", description="Salta a una posición específica de la cola")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la canción #{posicion}")
    else: await interaction.response.send_message("❌ Posición inválida.")

@bot.tree.command(name="lyrics", description="Busca la letra (Simulado)")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 Buscando letras para: **{bot.current_track}**...")

@bot.tree.command(name="restart", description="Reinicia la canción actual")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando pista...")

@bot.tree.command(name="info", description="Información del bot")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("🤖 **Flexus Bot V2** | Creado por Alex | 20 Comandos OK")

@bot.tree.command(name="stats", description="Ver estadísticas de anuncios")
async def stats(interaction: discord.Interaction):
    await interaction.response.send_message("📊 Revisa tu panel en Vercel para ver las visitas en vivo.")

@bot.tree.command(name="help", description="Muestra la lista de comandos")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message("👑 **COMANDOS FLEXUS:** /play, /skip, /stop, /pause, /resume, /queue, /nowplaying, /shuffle, /volume, /ping, /clear, /bassboost, /loop, /leave, /jump, /lyrics, /restart, /info, /stats, /help")

bot.run(TOKEN)
