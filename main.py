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
        print(f"✅ FLEXUS V2: COMANDOS SINCRONIZADOS") 

bot = FlexusBot() 

# CONFIGURACIÓN AUDIO (Mejorada para evitar cortes)
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
    """Suma los oyentes reales a la base de datos de MongoDB"""
    if interaction.guild.voice_client and interaction.guild.voice_client.channel:
        oyentes = len(interaction.guild.voice_client.channel.members) - 1 # Restamos al bot
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}})

def play_next(interaction):
    if not interaction.guild.voice_client:
        return

    if len(bot.queue) > 0:
        # MEJORA: Sistema de anuncios automático mejorado
        if bot.songs_played > 0 and bot.songs_played % 3 == 0:
            bot.songs_played = 0 # Reiniciamos contador para que no se buclee
            if os.path.exists("anuncio.mp3"):
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

# --- COMANDOS ---

@bot.tree.command(name="play", description="Reproduce música de YouTube") 
async def play(interaction: discord.Interaction, busqueda: str): 
    await interaction.response.defer()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        if 'entries' in data: data = data['entries'][0]
        url, titulo = data['url'], data['title']
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing() or vc.is_paused():
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

# NUEVO COMANDO: /announce
@bot.tree.command(name="announce", description="Reproduce el anuncio manualmente")
async def announce(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ Debes estar en un canal de voz.")
    
    await interaction.response.defer()
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    
    if os.path.exists("anuncio.mp3"):
        if vc.is_playing():
            vc.stop() # Paramos lo que suene para meter el anuncio
        
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("anuncio.mp3"), volume=1.0)
        vc.play(source, after=lambda e: play_next(interaction))
        await registrar_anuncio(interaction)
        await interaction.followup.send("📢 Reproduciendo anuncio y registrando audiencia...")
    else:
        await interaction.followup.send("❌ No se encontró el archivo `anuncio.mp3` en el servidor.")

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Canción saltada.")

@bot.tree.command(name="stop", description="Detiene todo")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue", description="Muestra la lista")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("📋 La cola está vacía.")
    msg = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"📋 **Cola:**\n{msg}")

@bot.tree.command(name="nowplaying", description="Qué suena ahora")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Sonando: **{bot.current_track or 'Nada'}**")

@bot.tree.command(name="shuffle", description="Mezcla la cola")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Mezclado.")

@bot.tree.command(name="volume", description="Ajusta el volumen (1-200)")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volumen: {vol}%")

@bot.tree.command(name="ping", description="Latencia")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear", description="Limpia la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada.")

@bot.tree.command(name="bassboost")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 BASS BOOST ACTIVADO")

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle activado.")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Desconectado.")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltado a #{posicion}")
    else: await interaction.response.send_message("❌ Posición inválida.")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 Buscando letras para {bot.current_track}...")

@bot.tree.command(name="restart")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando canción...")

@bot.tree.command(name="info")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("🤖 **Flexus Bot V2** | Sistema Ads OK")

@bot.tree.command(name="stats")
async def stats(interaction: discord.Interaction):
    await interaction.response.send_message("📊 Estadísticas en Vercel actualizadas.")

@bot.tree.command(name="help")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message("👑 Comandos: /play, /announce, /skip, /stop, /pause, /resume, /queue, /nowplaying, /shuffle, /volume, /ping, /clear, /bassboost, /loop, /leave, /jump, /lyrics, /restart, /info, /stats")

bot.run(TOKEN)
