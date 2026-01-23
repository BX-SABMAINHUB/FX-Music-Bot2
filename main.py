import discord 
from discord import app_commands, ui
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURACIÓN ---
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"

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
        self.last_track = None # Para recordar qué canción reseñar

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V3.4: AUDIO REPARADO + SISTEMA DE RESEÑAS") 

bot = FlexusBot() 

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
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
    reason = ui.TextInput(label="¿Qué te ha parecido?", style=discord.TextStyle.paragraph, placeholder="Escribe aquí tu opinión...")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rating = int(self.stars.value)
            if rating < 1 or rating > 5:
                return await interaction.response.send_message("❌ La puntuación debe ser entre 1 y 5.", ephemeral=True)
            
            review_data = {
                "user": interaction.user.name,
                "user_avatar": str(interaction.user.display_avatar.url),
                "song": self.song_title,
                "stars": rating,
                "message": self.reason.value,
                "date": discord.utils.utcnow()
            }
            await reviews_col.insert_one(review_data)
            await interaction.response.send_message(f"✅ ¡Gracias! Tu reseña se ha enviado a la web.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Introduce un número válido.", ephemeral=True)

class ReviewView(ui.View):
    def __init__(self, song_title):
        super().__init__(timeout=120)
        self.song_title = song_title

    @ui.button(label="✍️ Dejar Reseña", style=discord.ButtonStyle.success, emoji="⭐")
    async def leave_review(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReviewModal(self.song_title))

async def prompt_review(channel, song_title):
    if channel and song_title:
        embed = discord.Embed(description=f"🎶 **{song_title}** ha terminado. ¿Qué te pareció?", color=0x00ff77)
        await channel.send(embed=embed, view=ReviewView(song_title))

# --- LÓGICA DE AUDIO (CORREGIDA) ---

async def registrar_anuncio(guild):
    if guild.voice_client and guild.voice_client.channel:
        oyentes = len(guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(interaction):
    if not interaction.guild.voice_client: return
    
    # IMPORTANTE: Lanzamos la reseña de la canción que ACABA de terminar
    if bot.current_track:
        bot.last_track = bot.current_track
        asyncio.run_coroutine_threadsafe(prompt_review(interaction.channel, bot.last_track), bot.loop)

    canal = interaction.guild.voice_client.channel
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in canal.members)

    # Lógica de anuncios
    if bot.songs_played >= 3:
        bot.songs_played = 0
        if not es_vip and os.path.exists("anuncio.mp3"):
            bot.current_track = None # El anuncio no es una canción reseñable
            source = discord.FFmpegPCMAudio("anuncio.mp3")
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction.guild), bot.loop)
            return

    # Siguiente canción
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- COMANDOS Y SELECCIÓN ---

class SongSelect(ui.Select):
    def __init__(self, options_data):
        options = [discord.SelectOption(label=d.get('title')[:90], description=f"Canal: {d.get('uploader')[:30]}", value=str(i), emoji="🎶") for i, d in enumerate(options_data)]
        super().__init__(placeholder="💎 Elige tu canción...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected = self.options_data[int(self.values[0])]
        info = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(selected['webpage_url'], download=False))
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing():
            bot.queue.append((info['url'], info['title']))
            await interaction.followup.send(f"✅ Añadida a la cola: **{info['title']}**")
        else:
            bot.songs_played += 1
            bot.current_track = info['title']
            vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            await interaction.followup.send(f"▶️ Reproduciendo ahora: **{info['title']}**")

class SongView(ui.View):
    def __init__(self, options_data):
        super().__init__()
        self.add_item(SongSelect(options_data))

@bot.tree.command(name="play", description="Busca canciones")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{cancion}", download=False))
        view = SongView(data['entries'])
        await interaction.followup.send(f"🎯 Resultados para: **{cancion}**", view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="skip", description="Salta la canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop() # Esto activa automáticamente play_next y la reseña
        await interaction.response.send_message("⏭️ **Canción saltada.**")

@bot.tree.command(name="stop", description="Detiene todo")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    bot.current_track = None
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ **Bot detenido.**")

# --- OTROS COMANDOS ---
@bot.tree.command(name="pause", description="Pausa")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ **Pausado.**")

@bot.tree.command(name="resume", description="Reanuda")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ **Reanudado.**")

@bot.tree.command(name="stats", description="Ver audiencia")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    v = data["views"] if data else 0
    await interaction.response.send_message(f"📊 **Impacto Total:** {v} oyentes.")

@bot.tree.command(name="help", description="Comandos")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("👑 **Comandos Flexus:** `play, skip, stop, pause, resume, stats, info`")

bot.run(TOKEN)
