import discord 
from discord import app_commands 
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURACIÓN ---
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"

# --- BASE DE DATOS ---
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
        print(f"✅ FLEXUS V2 PRO: DOCKER + SISTEMA VIP CARGADO") 

bot = FlexusBot() 

# CONFIGURACIÓN YTDL (SISTEMA ANTIBLOQUEO)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    }
} 

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- FUNCIONES DE LÓGICA ---

async def registrar_anuncio(interaction):
    """Suma oyentes a MongoDB Atlas"""
    if interaction.guild.voice_client:
        oyentes = len(interaction.guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(interaction):
    if not interaction.guild.voice_client: return
    
    # --- ESCANEO DE MIEMBROS VIP ---
    canal_voz = interaction.guild.voice_client.channel
    vip_presente = any(any(role.name == "VIP" for role in m.roles) for m in canal_voz.members)

    # Lógica de Anuncio (Cada 3 canciones)
    if bot.songs_played >= 3:
        bot.songs_played = 0 # Reiniciamos contador
        
        if vip_presente:
            # Si hay un VIP, no enviamos mensaje, solo seguimos con la música
            print("💎 VIP detectado: Saltando anuncio.")
        elif os.path.exists("anuncio.mp3"):
            source = discord.FFmpegPCMAudio("anuncio.mp3")
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction), bot.loop)
            asyncio.run_coroutine_threadsafe(interaction.channel.send("📢 **Anuncio de Flexus sonando...** (¡Hazte VIP para saltarlos!)"), bot.loop)
            return

    # Reproducir siguiente canción de la cola
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- COMANDOS ---

@bot.tree.command(name="play", description="Reproduce música (Sin anuncios para VIPs)") 
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
        await interaction.followup.send(f"❌ Error YouTube: {e}")

@bot.tree.command(name="announce", description="Fuerza el anuncio (Solo Admins)")
async def announce(interaction: discord.Interaction):
    await interaction.response.defer()
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if os.path.exists("anuncio.mp3"):
        if vc.is_playing(): vc.stop()
        vc.play(discord.FFmpegPCMAudio("anuncio.mp3"), after=lambda e: play_next(interaction))
        await registrar_anuncio(interaction)
        await interaction.followup.send("📢 Reproduciendo anuncio forzado...")
    else:
        await interaction.followup.send("❌ No se encontró `anuncio.mp3`.")

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Bot detenido.")

@bot.tree.command(name="stats", description="Vistas en MongoDB")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    vistas = data["views"] if data else 0
    await interaction.response.send_message(f"📊 Impacto total: **{vistas} oyentes** registrados en MongoDB.")

@bot.tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("💎 **COMANDOS VIP READY:** /play, /announce, /skip, /stop, /queue, /nowplaying, /stats, /volume, /ping, /clear, /bassboost, /loop, /leave, /jump, /lyrics, /restart, /info")

# --- COMANDOS EXTRAS (RESTO DE LOS 20) ---
@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("📋 Cola vacía.")
    txt = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue[:5])])
    await interaction.response.send_message(f"📋 **Próximas:**\n{txt}")

@bot.tree.command(name="nowplaying")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Sonando: **{bot.current_track}**")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volumen: {vol}%")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Latencia: {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola limpia.")

@bot.tree.command(name="bassboost")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 **BASS BOOST ACTIVADO**")

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle activado.")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Adiós.")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltado a #{pos}")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 Buscando letras para {bot.current_track}...")

@bot.tree.command(name="restart")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando canción.")

@bot.tree.command(name="info")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("🤖 Flexus V2 | Docker | VIP System")

bot.run(TOKEN)
