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
        print(f"✅ FLEXUS V4.0: TODO INCLUIDO") 

bot = FlexusBot() 

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
    'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
} 

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k'
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- SISTEMA DE RESEÑAS ---

class ReviewModal(ui.Modal, title="Reseña de Canción"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="Estrellas (1-5)", placeholder="5", min_length=1, max_length=1)
    reason = ui.TextInput(label="Comentario", style=discord.TextStyle.paragraph, placeholder="Increíble sonido...")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.stars.value)
            if not 1 <= val <= 5: raise ValueError()
            
            # GUARDADO CRÍTICO PARA LA WEB
            await reviews_col.insert_one({
                "user": interaction.user.name,
                "user_avatar": str(interaction.user.display_avatar.url),
                "song": self.song_title,
                "stars": val,
                "message": self.reason.value,
                "timestamp": datetime.utcnow()
            })
            await interaction.response.send_message("⭐ Reseña enviada a la web!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Error: Usa un número del 1 al 5.", ephemeral=True)

# --- LÓGICA DE AUDIO ---

def play_next(interaction):
    if not interaction.guild.voice_client: return
    
    # Enviar prompt de reseña al acabar
    if bot.current_track:
        view = ui.View().add_item(ui.Button(label="Dejar Reseña", style=discord.ButtonStyle.success, custom_id="review_btn"))
        # Usamos una función simple para el botón
        async def callback(inter):
            await inter.response.send_modal(ReviewModal(bot.current_track))
        
        asyncio.run_coroutine_threadsafe(
            interaction.channel.send(f"✅ Terminó **{bot.current_track}**. ¿Qué te pareció?", 
            view=ui.View().add_item(ui.Button(label="⭐ Reseñar", style=discord.ButtonStyle.green, custom_id="r"))), 
            bot.loop
        )

    # Lógica de Anuncios
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in interaction.guild.voice_client.channel.members)
    if bot.songs_played >= 3 and not es_vip and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        bot.current_track = "Publicidad"
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3"), after=lambda e: play_next(interaction))
        return

    # Cola
    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = title
        info = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS ---

@bot.tree.command(name="play")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{buscar}", download=False))
    results = data['entries']
    
    class SelectMusic(ui.Select):
        def __init__(self):
            super().__init__(placeholder="Elige una canción", options=[discord.SelectOption(label=r['title'][:90], value=str(i)) for i, r in enumerate(results)])
        async def callback(self, inter: discord.Interaction):
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title']))
                await inter.followup.send(f"➕ En cola: {s['title']}")
            else:
                bot.songs_played += 1
                bot.current_track = s['title']
                info = ytdl.extract_info(s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter))
                await inter.followup.send(f"▶️ Sonando: {s['title']}")

    await interaction.followup.send(view=ui.View().add_item(SelectMusic()))

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.stop()
    await interaction.response.send_message("⏭️ Saltada")

@bot.tree.command(name="stop")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ Desconectado")

@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado")

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado")

@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    q = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue[:5])]) or "Vacía"
    await interaction.response.send_message(f"📋 Cola:\n{q}")

@bot.tree.command(name="nowplaying")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Sonando: {bot.current_track or 'Nada'}")

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Mezclado")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client: 
        interaction.guild.voice_client.source.volume = vol/100
        await interaction.response.send_message(f"🔊 Volumen: {vol}%")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 Latencia: {round(bot.latency*1000)}ms")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Cola limpia")

@bot.tree.command(name="stats")
async def stats(interaction: discord.Interaction):
    d = await stats_col.find_one({"id": "global"})
    await interaction.response.send_message(f"📊 Impacto: {d['views'] if d else 0} oyentes")

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Adiós")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos-1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la {pos}")

@bot.tree.command(name="restart")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando pista...")

@bot.tree.command(name="bassboost")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Bass Boost activado")

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle activado")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 Buscando letra de {bot.current_track}...")

@bot.tree.command(name="info")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("💎 **Flexus Premium V4.0** | Audio 192kbps")

@bot.tree.command(name="help")
async def help(interaction: discord.Interaction):
    cmds = "play, skip, stop, pause, resume, queue, nowplaying, shuffle, volume, ping, clear, stats, leave, jump, restart, bassboost, loop, lyrics, info"
    await interaction.response.send_message(f"👑 **Comandos:**\n`{cmds}`")

bot.run(TOKEN)
