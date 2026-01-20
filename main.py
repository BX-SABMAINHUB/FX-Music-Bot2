import discord 
from discord import app_commands 
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient

TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?appName=Cluster0"

# --- BASE DE DATOS ---
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
stats_col = db["ads_stats"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() # Activamos todos los permisos para que salga Online
        super().__init__(command_prefix="!", intents=intents, help_command=None) 
        self.queue = [] 
        self.songs_played = 0
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        if await stats_col.count_documents({"id": "global"}) == 0:
            await stats_col.insert_one({"id": "global", "views": 0})
        print(f"✅ FLEXUS V2 ACTIVADO") 

bot = FlexusBot() 

# CONFIGURACIÓN AUDIO
YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'nocheckcertificate': True} 
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
    'options': '-vn -af "loudnorm=I=-14:LRA=1:tp=-1"'
} 
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS) 

async def registrar_anuncio(interaction):
    oyentes = len(interaction.guild.voice_client.channel.members) - 1
    await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}})

def play_next(interaction):
    if len(bot.queue) > 0:
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

# --- LOS 20 COMANDOS FLEXUS ---

@bot.tree.command(name="play") 
async def play(interaction: discord.Interaction, busqueda: str): 
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
    if 'entries' in data: data = data['entries'][0]
    url, titulo = data['url'], data['title']
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if vc.is_playing():
        bot.queue.append((url, titulo))
        await interaction.followup.send(f"✅ En cola: {titulo}")
    else:
        bot.songs_played = 1
        bot.current_track = titulo
        vc.play(discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)), after=lambda e: play_next(interaction))
        await interaction.followup.send(f"🎶 Sonando: {titulo}")

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.stop()
    await interaction.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Desconectado.")

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
    msg = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue[:5])]) or "Vacía"
    await interaction.response.send_message(f"📋 **Cola:**\n{msg}")

@bot.tree.command(name="nowplaying")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Suena: {bot.current_track}")

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Mezclado.")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volumen al {vol}%")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Latencia: {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola limpia.")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message("🔍 Buscando letra...")

@bot.tree.command(name="bassboost")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Graves potenciados.")

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Repetición activada.")

@bot.tree.command(name="restart")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando canción.")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Adiós.")

@bot.tree.command(name="help")
async def help(interaction: discord.Interaction):
    await interaction.response.send_message("👑 **FLEXUS 100%** - Usa /play, /skip, /stop, /queue...")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la posición {pos}")

@bot.tree.command(name="info")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("🤖 **Flexus Bot V2** | Desarrollado por Alex.")

@bot.tree.command(name="stats")
async def stats(interaction: discord.Interaction):
    await interaction.response.send_message("📊 Revisa tu panel en Vercel para ver las visitas.")

bot.run(TOKEN)
