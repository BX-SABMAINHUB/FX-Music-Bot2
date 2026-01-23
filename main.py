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
        self.last_text_channel = None # Guardamos el canal para enviar las reseñas

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V3.4: SISTEMA DE RESEÑAS REPARADO") 

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
    reason = ui.TextInput(label="¿Por qué te ha gustado?", style=discord.TextStyle.paragraph, placeholder="Escribe tu opinión...")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rating = int(self.stars.value)
            if rating < 1 or rating > 5:
                return await interaction.response.send_message("❌ Puntuación inválida (1-5).", ephemeral=True)
            
            # Guardar en MongoDB (Misma DB que anuncios)
            await reviews_col.insert_one({
                "user": interaction.user.name,
                "user_id": interaction.user.id,
                "song": self.song_title,
                "stars": rating,
                "message": self.reason.value,
                "timestamp": discord.utils.utcnow()
            })
            await interaction.response.send_message(f"✅ Reseña de {rating}⭐ enviada a la web.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Error: Introduce un número.", ephemeral=True)

class ReviewView(ui.View):
    def __init__(self, song_title):
        super().__init__(timeout=180)
        self.song_title = song_title

    @ui.button(label="✍️ Valorar esta canción", style=discord.ButtonStyle.success, emoji="⭐")
    async def leave_review(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReviewModal(self.song_title))

async def enviar_peticion_reseña(song_title):
    """Envía el mensaje de reseña al canal donde se pidió música"""
    if bot.last_text_channel and song_title:
        embed = discord.Embed(
            title="⭐ ¿Qué tal la música?",
            description=f"Acaba de sonar: **{song_title}**\n\nAyúdanos a mejorar valorando la canción.",
            color=0xffd700
        )
        await bot.last_text_channel.send(embed=embed, view=ReviewView(song_title))

# --- LÓGICA DE AUDIO ---

async def registrar_anuncio(guild):
    if guild.voice_client and guild.voice_client.channel:
        oyentes = len(guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(guild):
    if not guild.voice_client: return
    
    # 1. DISPARAR RESEÑA DE LA CANCIÓN ANTERIOR
    if bot.current_track:
        asyncio.run_coroutine_threadsafe(enviar_peticion_reseña(bot.current_track), bot.loop)

    # 2. SISTEMA DE ANUNCIOS / SIGUIENTE CANCIÓN
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in guild.voice_client.channel.members)

    if bot.songs_played >= 3:
        bot.songs_played = 0
        if not es_vip and os.path.exists("anuncio.mp3"):
            source = discord.FFmpegPCMAudio("anuncio.mp3")
            # Cuando acaba el anuncio, NO pedimos reseña (bot.current_track se mantiene)
            guild.voice_client.play(source, after=lambda e: play_next(guild))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(guild), bot.loop)
            return

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        guild.voice_client.play(source, after=lambda e: play_next(guild))
    else:
        bot.current_track = None

# --- COMANDOS ---

class SongSelect(ui.Select):
    def __init__(self, options_data):
        options = [discord.SelectOption(label=d['title'][:90], emoji="🎶", value=str(i)) for i, d in enumerate(options_data)]
        super().__init__(placeholder="💎 Elige la canción...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        bot.last_text_channel = interaction.channel # GUARDAMOS EL CANAL
        
        selected = self.options_data[int(self.values[0])]
        info = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(selected['webpage_url'], download=False))
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing():
            bot.queue.append((info['url'], info['title']))
            await interaction.followup.send(f"✅ **Añadida:** {info['title']}")
        else:
            bot.songs_played += 1
            bot.current_track = info['title']
            vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction.guild))
            await interaction.followup.send(f"▶️ **Reproduciendo:** {info['title']}")

class SongView(ui.View):
    def __init__(self, options_data):
        super().__init__()
        self.add_item(SongSelect(options_data))

@bot.tree.command(name="play", description="Busca música")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{cancion}", download=False))
    await interaction.followup.send(view=SongView(data['entries']))

@bot.tree.command(name="skip", description="Salta la canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop() # Esto activará play_next y por tanto la reseña
        await interaction.response.send_message("⏭️ **Saltada.**")

@bot.tree.command(name="stop", description="Detener")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    bot.current_track = None
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ **Detenido.**")

# RESTO DE COMANDOS (IGUALES AL ORIGINAL)
@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message("⏸️")

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message("▶️")

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(f"🎧: {bot.current_track}")

@bot.tree.command(name="help")
async def help_cmd(i: discord.Interaction):
    await i.response.send_message("👑 Comandos: play, skip, stop, pause, resume, nowplaying, info")

@bot.tree.command(name="info")
async def info(i: discord.Interaction):
    await i.response.send_message("Flexus V3.4 Premium - Sistema de Reseñas en Vercel Activo")

bot.run(TOKEN)
