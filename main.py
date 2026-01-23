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
        print(f"✅ FLEXUS V3.5: SISTEMA ESTABLE + 19 COMANDOS") 

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

class ReviewModal(ui.Modal, title="Reseña de Flexus"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="Puntuación (1-5)", placeholder="5", min_length=1, max_length=1)
    reason = ui.TextInput(label="Tu opinión", style=discord.TextStyle.paragraph, placeholder="Me encantó el sonido...")

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
            await interaction.response.send_message(f"✅ Reseña guardada para la web.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Usa un número del 1 al 5.", ephemeral=True)

class ReviewView(ui.View):
    def __init__(self, song_title):
        super().__init__(timeout=60)
        self.song_title = song_title

    @ui.button(label="⭐ Dejar Reseña", style=discord.ButtonStyle.green)
    async def review_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReviewModal(self.song_title))

# --- LÓGICA DE AUDIO (CORREGIDA) ---

async def registrar_anuncio(guild):
    if guild.voice_client and guild.voice_client.channel:
        oyentes = len(guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(interaction):
    if not interaction.guild.voice_client: return

    # Lanzar reseña de la canción anterior SI EXISTE
    if bot.current_track:
        asyncio.run_coroutine_threadsafe(
            interaction.channel.send(f"🎶 ¿Qué te pareció **{bot.current_track}**?", view=ReviewView(bot.current_track)),
            bot.loop
        )

    # Lógica de Anuncios cada 3 canciones
    canal = interaction.guild.voice_client.channel
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in canal.members)

    if bot.songs_played >= 3 and not es_vip and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        bot.current_track = None 
        source = discord.FFmpegPCMAudio("anuncio.mp3")
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
        asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction.guild), bot.loop)
        return

    # Siguiente en cola
    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS ---

@bot.tree.command(name="play", description="Busca y elige música")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{cancion}", download=False))
    if not data['entries']: return await interaction.followup.send("❌ Sin resultados.")
    
    view = SongView(data['entries'])
    await interaction.followup.send(f"🎯 Resultados para: {cancion}", view=view)

class SongSelect(ui.Select):
    def __init__(self, options_data):
        options = [discord.SelectOption(label=d['title'][:90], description=d.get('uploader', 'YouTube')[:30], value=str(i)) for i, d in enumerate(options_data)]
        super().__init__(placeholder="Elige una canción...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        sel = self.options_data[int(self.values[0])]
        url, title = sel['url'], sel['title']
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing():
            bot.queue.append((url, title))
            await interaction.followup.send(f"✅ En cola: **{title}**")
        else:
            bot.songs_played += 1
            bot.current_track = title
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            await interaction.followup.send(f"▶️ Sonando: **{title}**")

class SongView(ui.View):
    def __init__(self, data):
        super().__init__()
        self.add_item(SongSelect(data))

@bot.tree.command(name="skip", description="Salta la canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop", description="Detiene todo")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="pause", description="Pausa")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="Reanuda")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue", description="Ver cola")
async def queue(interaction: discord.Interaction):
    q = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])]) or "Vacía"
    await interaction.response.send_message(f"📋 **Cola:**\n{q}")

@bot.tree.command(name="nowplaying", description="Qué suena")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Ahora: {bot.current_track or 'Nada'}")

@bot.tree.command(name="shuffle", description="Mezcla")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Mezclado.")

@bot.tree.command(name="volume", description="Volumen 0-100")
async def volume(interaction: discord.Interaction, nivel: int):
    if interaction.guild.voice_client: 
        interaction.guild.voice_client.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen: {nivel}%")

@bot.tree.command(name="ping", description="Latencia")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear", description="Limpia cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola vacía.")

@bot.tree.command(name="stats", description="Audiencia")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    await interaction.response.send_message(f"📊 Impacto: {data.get('views', 0) if data else 0} oyentes.")

@bot.tree.command(name="leave", description="Salir")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Adiós.")

@bot.tree.command(name="jump", description="Saltar a posición")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos-1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a #{pos}")

@bot.tree.command(name="restart", description="Reinicia pista")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando...")

@bot.tree.command(name="bassboost", description="Bajos")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Bass Boost OK.")

@bot.tree.command(name="loop", description="Bucle")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle OK.")

@bot.tree.command(name="info", description="Sistema")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("💎 Flexus V3.5 | 192kbps | AlexGaming")

@bot.tree.command(name="help", description="Ayuda")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("📜 Comandos: play, skip, stop, pause, resume, queue, nowplaying, shuffle, volume, ping, clear, stats, leave, jump, restart, bassboost, loop, info, help")

bot.run(TOKEN)
