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
reviews_col = db["reviews"] # Colección vinculada a tu web de Vercel

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="/", intents=intents) 
        self.queue = [] 
        self.songs_played = 0
        self.current_track = None
        self.text_channel = None # Guardamos el canal para enviar la reseña

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V3.4: RESEÑAS ACTIVAS Y VINCULADAS A VERCEL") 

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
    reason = ui.TextInput(label="¿Qué te ha parecido?", style=discord.TextStyle.paragraph, placeholder="Me gustó mucho el ritmo...")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rating = int(self.stars.value)
            if rating < 1 or rating > 5:
                return await interaction.response.send_message("❌ La puntuación debe ser entre 1 y 5.", ephemeral=True)
            
            # Datos exactos para que aparezcan en https://fx-music-bot2.vercel.app/
            review_data = {
                "user": interaction.user.name,
                "user_avatar": str(interaction.user.display_avatar.url),
                "song": self.song_title,
                "stars": rating,
                "message": self.reason.value,
                "date": discord.utils.utcnow()
            }
            await reviews_col.insert_one(review_data)
            await interaction.response.send_message(f"✅ ¡Gracias! Tu reseña aparecerá en la web.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Introduce un número válido.", ephemeral=True)

class ReviewView(ui.View):
    def __init__(self, song_title):
        super().__init__(timeout=120)
        self.song_title = song_title

    @ui.button(label="⭐ Dejar Reseña", style=discord.ButtonStyle.success)
    async def leave_review(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReviewModal(self.song_title))

async def ask_for_review(channel, song_title):
    """Función separada para evitar errores de contexto"""
    if channel and song_title:
        embed = discord.Embed(
            title="🏁 Canción Finalizada",
            description=f"¿Qué te pareció **{song_title}**?\nTu opinión nos ayuda a mejorar.",
            color=0x00ff77
        )
        await channel.send(embed=embed, view=ReviewView(song_title))

# --- LÓGICA DE AUDIO ---

async def registrar_anuncio(guild):
    if guild.voice_client and guild.voice_client.channel:
        oyentes = len(guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(guild):
    if not guild.voice_client: return
    
    # TRIGGER DE RESEÑA: Al acabar (natural o skip), preguntamos
    if bot.current_track and bot.text_channel:
        asyncio.run_coroutine_threadsafe(ask_for_review(bot.text_channel, bot.current_track), bot.loop)

    canal = guild.voice_client.channel
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in canal.members)

    if bot.songs_played >= 3:
        bot.songs_played = 0
        if not es_vip and os.path.exists("anuncio.mp3"):
            source = discord.FFmpegPCMAudio("anuncio.mp3")
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

# --- COMANDOS REESCRITOS ---

@bot.tree.command(name="play", description="Busca y reproduce música")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    bot.text_channel = interaction.channel # Guardamos el canal para la reseña posterior
    
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{cancion}", download=False))
        results = data['entries']
        if not results: return await interaction.followup.send("❌ Sin resultados.")
        
        view = SongView(results)
        await interaction.followup.send(f"🎯 Resultados para: **{cancion}**", view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="skip", description="Salta la canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop() # Al parar, el 'after' de play_next disparará la reseña
        await interaction.response.send_message("⏭️ **Saltando pista...**")

# --- INTERFAZ DE SELECCIÓN ---

class SongSelect(ui.Select):
    def __init__(self, options_data):
        options = [discord.SelectOption(label=d.get('title')[:90], description=f"Canal: {d.get('uploader')[:30]}", value=str(i), emoji="🎶") for i, d in enumerate(options_data)]
        super().__init__(placeholder="💎 Elige la canción...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        sel = self.options_data[int(self.values[0])]
        info = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(sel.get('webpage_url') or sel.get('url'), download=False))
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        if vc.is_playing():
            bot.queue.append((info['url'], info['title']))
            await interaction.followup.send(f"✅ Añadida: **{info['title']}**")
        else:
            bot.songs_played += 1
            bot.current_track = info['title']
            vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction.guild))
            await interaction.followup.send(f"▶️ Reproduciendo: **{info['title']}**")

class SongView(ui.View):
    def __init__(self, options_data):
        super().__init__()
        self.add_item(SongSelect(options_data))

# --- RESTO DE COMANDOS (IGUALES) ---
@bot.tree.command(name="stop", description="Detiene el bot")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    bot.current_track = None
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Bot detenido.")

@bot.tree.command(name="pause", description="Pausa")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Reanudar")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="stats", description="Ver estadísticas")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    v = data["views"] if data else 0
    await interaction.response.send_message(f"📊 Impacto Total: {v} oyentes.")

@bot.tree.command(name="help", description="Ayuda")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("👑 **Comandos Flexus:**\n`play, skip, stop, pause, resume, stats, info`")

bot.run(TOKEN)
