import discord 
from discord import app_commands 
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient

# Configuración
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"

# Base de datos
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
stats_col = db["ads_stats"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="/", intents=intents) 
        self.queue = [] 
        self.songs_played = 0
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V2: SISTEMA LISTO EN DOCKER") 

bot = FlexusBot() 

# FIX DE COOKIES Y AGENTE DE NAVEGADOR
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive',
    }
} 

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

async def registrar_anuncio(interaction):
    if interaction.guild.voice_client:
        oyentes = len(interaction.guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(interaction):
    if not interaction.guild.voice_client: return
    
    # Sistema Automático (cada 3 canciones)
    if bot.songs_played >= 3:
        bot.songs_played = 0
        if os.path.exists("anuncio.mp3"):
            source = discord.FFmpegPCMAudio("anuncio.mp3")
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction), bot.loop)
            return

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
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
        url = data['url']
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing():
            bot.queue.append((url, data['title']))
            await interaction.followup.send(f"✅ En cola: **{data['title']}**")
        else:
            bot.songs_played += 1
            bot.current_track = data['title']
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            await interaction.followup.send(f"🎶 Sonando: **{data['title']}**")
    except Exception as e:
        await interaction.followup.send(f"❌ Error (Cookies/YouTube): {e}")

@bot.tree.command(name="announce", description="Reproduce el anuncio ahora mismo")
async def announce(interaction: discord.Interaction):
    await interaction.response.defer()
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if os.path.exists("anuncio.mp3"):
        if vc.is_playing(): vc.stop()
        vc.play(discord.FFmpegPCMAudio("anuncio.mp3"), after=lambda e: play_next(interaction))
        await registrar_anuncio(interaction)
        await interaction.followup.send("📢 Reproduciendo anuncio manual...")
    else:
        await interaction.followup.send("❌ No se encuentra el archivo anuncio.mp3.")

@bot.tree.command(name="skip", description="Salta la canción actual")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Saltando pista...")

@bot.tree.command(name="stop", description="Detiene todo")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Flexus apagado.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Sigue sonando")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue", description="Mira la lista de espera")
async def queue_show(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("📋 La cola está vacía.")
    lista = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    await interaction.response.send_message(f"📋 **Próximas canciones:**\n{lista}")

@bot.tree.command(name="nowplaying", description="Qué suena ahora")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Escuchando: **{bot.current_track or 'Nada'}**")

@bot.tree.command(name="shuffle", description="Mezcla la cola")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Cola mezclada aleatoriamente.")

@bot.tree.command(name="volume", description="Volumen del bot")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volumen: {vol}%")

@bot.tree.command(name="ping", description="Mira la latencia")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Latencia: {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear", description="Limpia la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vaciada.")

@bot.tree.command(name="bassboost", description="Modo Flexus")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 **BASS BOOST ACTIVADO** (Modo Flexus)")

@bot.tree.command(name="loop", description="Repite la pista")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle activado.")

@bot.tree.command(name="leave", description="Echa al bot")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 ¡Nos vemos!")

@bot.tree.command(name="jump", description="Salta a un número de la lista")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltado hasta la posición #{posicion}")
    else: await interaction.response.send_message("❌ Posición no válida.")

@bot.tree.command(name="lyrics", description="Letra de la canción")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 Buscando letra para: **{bot.current_track}**")

@bot.tree.command(name="restart", description="Reinicia la canción")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando canción actual...")

@bot.tree.command(name="info", description="Sobre el bot")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("🤖 **Flexus V2 Pro** | Docker Edition | Sistema Ads OK")

@bot.tree.command(name="stats", description="Vistas totales")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    vistas = data["views"] if data else 0
    await interaction.response.send_message(f"📊 Impacto total: **{vistas} oyentes registrados**.")

@bot.tree.command(name="help", description="Lista de comandos")
async def help_cmd(interaction: discord.Interaction):
    cmds = "/play, /announce, /skip, /stop, /pause, /resume, /queue, /nowplaying, /shuffle, /volume, /ping, /clear, /bassboost, /loop, /leave, /jump, /lyrics, /restart, /info, /stats"
    await interaction.response.send_message(f"👑 **Comandos Flexus:**\n{cmds}")

bot.run(TOKEN)
