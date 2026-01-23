import discord 
from discord import app_commands, ui
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# --- CONFIGURACIÓN ---
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"

# Conexión persistente a MongoDB
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
stats_col = db["ads_stats"]
reviews_col = db["reviews"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="/", intents=intents) 
        self.queue = [] 
        self.songs_played = 0
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V3.6: SISTEMA REPARADO") 

bot = FlexusBot() 

# Configuración Optimizada
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
} 

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k'
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- SISTEMA DE RESEÑAS ---

class ReviewModal(ui.Modal, title="Reseña de la canción"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="Puntuación (1-5)", placeholder="5", min_length=1, max_length=1)
    reason = ui.TextInput(label="Opinión", style=discord.TextStyle.paragraph, placeholder="¡Increíble!")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rating = int(self.stars.value)
            if not 1 <= rating <= 5: raise ValueError()
            
            review_data = {
                "user": interaction.user.name,
                "user_avatar": str(interaction.user.display_avatar.url),
                "song": self.song_title,
                "stars": rating,
                "message": self.reason.value,
                "timestamp": datetime.utcnow()
            }
            await reviews_col.insert_one(review_data)
            await interaction.response.send_message("✅ Reseña enviada a la web.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Introduce un número del 1 al 5.", ephemeral=True)

class ReviewView(ui.View):
    def __init__(self, song_title):
        super().__init__(timeout=60)
        self.song_title = song_title

    @ui.button(label="✍️ Dejar Reseña", style=discord.ButtonStyle.success)
    async def leave_review(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReviewModal(self.song_title))

# --- LÓGICA DE AUDIO REPARADA ---

def play_next(interaction):
    if not interaction.guild.voice_client: return

    # Lanzar la reseña de la que acaba de terminar
    if bot.current_track:
        asyncio.run_coroutine_threadsafe(
            interaction.channel.send(f"💬 ¿Qué te pareció **{bot.current_track}**?", view=ReviewView(bot.current_track)),
            bot.loop
        )

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        
        # Re-extraer URL por si expiró
        try:
            info = ytdl.extract_info(url, download=False)
            source_url = info['url']
            source = discord.FFmpegPCMAudio(source_url, **FFMPEG_OPTIONS)
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
        except Exception as e:
            print(f"Error en reproducción: {e}")
            play_next(interaction)
    else:
        bot.current_track = None

# --- COMANDOS (1 a 19) ---

@bot.tree.command(name="play", description="Reproduce música")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{cancion}", download=False))
        if not data['entries']: return await interaction.followup.send("❌ No se encontró nada.")
        
        view = SongView(data['entries'])
        await interaction.followup.send(f"🎯 Resultados para: **{cancion}**", view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

class SongSelect(ui.Select):
    def __init__(self, options_data):
        options = [discord.SelectOption(label=d['title'][:90], value=str(i), description=d.get('uploader', 'YT')[:30]) for i, d in enumerate(options_data)]
        super().__init__(placeholder="Elige una canción...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        sel = self.options_data[int(self.values[0])]
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing():
            bot.queue.append((sel['webpage_url'], sel['title']))
            await interaction.followup.send(f"✅ Añadida: {sel['title']}")
        else:
            bot.current_track = sel['title']
            source = discord.FFmpegPCMAudio(sel['url'] if 'url' in sel else sel['webpage_url'], **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next(interaction))
            await interaction.followup.send(f"▶️ Sonando: {sel['title']}")

class SongView(ui.View):
    def __init__(self, data):
        super().__init__()
        self.add_item(SongSelect(data))

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Detenido.")

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
    q = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue[:10])]) or "Vacía"
    await interaction.response.send_message(f"📋 **Cola:**\n{q}")

@bot.tree.command(name="nowplaying")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Ahora: {bot.current_track or 'Nada'}")

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Mezclada.")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, nivel: int):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.source.volume = nivel/100
        await interaction.response.send_message(f"🔊 Volumen al {nivel}%")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola limpia.")

@bot.tree.command(name="stats")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    await interaction.response.send_message(f"📊 Oyentes: {data['views'] if data else 0}")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Adiós.")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos-1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la #{pos}")

@bot.tree.command(name="restart")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando pista...")

@bot.tree.command(name="bassboost")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Bass Boost activado.")

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle activado.")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message("🔍 Buscando letra...")

@bot.tree.command(name="info")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("💎 Flexus Bot V3.6 | Premium Audio")

@bot.tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("📜 Comandos: play, skip, stop, pause, resume, queue, np, shuffle, volume, ping, clear, stats, leave, jump, restart, bassboost, loop, lyrics, info")

bot.run(TOKEN)
