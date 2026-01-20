import discord 
from discord import app_commands 
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
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
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))

# --- COMANDOS PRINCIPALES ---

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
        await interaction.followup.send("❌ No se encuentra el archivo anuncio.mp3 en el contenedor.")

# (Aquí puedes pegar el resto de tus comandos skip, stop, etc.)

bot.run(TOKEN)
