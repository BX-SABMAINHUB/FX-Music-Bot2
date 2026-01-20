import discord 
from discord import app_commands 
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient # Necesitas esto para la web

TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?appName=Cluster0"

# --- CONEXIÓN A BASE DE DATOS ---
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
stats_col = db["ads_stats"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.default() 
        intents.message_content = True 
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.playlists = {} 
        self.current_track = None
        self.songs_played = 0 # Contador para los anuncios

    async def setup_hook(self): 
        await self.tree.sync() 
        # Inicializa el contador en la nube si no existe
        if await stats_col.count_documents({"id": "global"}) == 0:
            await stats_col.insert_one({"id": "global", "views": 0})
        print(f"✅ FLEXUS V2 (God Mode) conectado como {self.user}") 

bot = FlexusBot() 

YTDL_OPTIONS = { 
    'format': 'bestaudio/best', 
    'noplaylist': True, 
    'quiet': True, 
    'default_search': 'ytsearch', 
    'nocheckcertificate': True,
    'extractor_args': {'youtube': {'player_client': ['ios']}},
} 

FFMPEG_OPTIONS = { 
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 20M -analyzeduration 20M', 
    'options': '-vn -b:a 320k -af "loudnorm=I=-14:LRA=1:tp=-1"', 
} 

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

# --- FUNCIÓN PARA REGISTRAR VISTAS EN LA WEB ---
async def registrar_anuncio(interaction):
    if interaction.guild.voice_client:
        oyentes = len(interaction.guild.voice_client.channel.members) - 1
        if oyentes > 0:
            await stats_col.update_one({"id": "global"}, {"$inc": {"views": oyentes}})

def play_next(interaction):
    if len(bot.queue) > 0:
        # LÓGICA DE ANUNCIO: Cada 3 canciones
        if bot.songs_played > 0 and bot.songs_played % 3 == 0:
            bot.songs_played += 1 # Para que no se repita
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("anuncio.mp3"), volume=1.2)
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            # Registramos en MongoDB
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction), bot.loop)
            return

        url, titulo = bot.queue.pop(0)
        bot.current_track = titulo
        bot.songs_played += 1
        vc = interaction.guild.voice_client
        if vc:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=1.0)
            vc.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- COMANDOS ---

@bot.tree.command(name="play", description="Música FLEXUS 100%") 
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
            await interaction.followup.send(f"✅ En cola: **{titulo}**") 
        else:
            bot.current_track = titulo
            bot.songs_played = 1 # Empezamos a contar
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), volume=1.0)
            vc.play(source, after=lambda e: play_next(interaction)) 
            await interaction.followup.send(f"🎶 Sonando: **{titulo}**") 
    except: 
        await interaction.followup.send("❌ Error.") 

# ... (El resto de tus comandos volume, skip, stop siguen igual) ...

bot.run(TOKEN)
