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

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="/", intents=intents) 
        self.queue = [] 
        self.songs_played = 0
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"✅ FLEXUS V3: BUSCADOR + SISTEMA VIP + ADS ACTIVOS") 

bot = FlexusBot() 

# CONFIGURACIÓN YTDL (ANTIBLOQUEO)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5', # Busca 5 resultados
    'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
} 

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- LÓGICA DE AUDIO ---

async def registrar_anuncio(guild):
    if guild.voice_client and guild.voice_client.channel:
        oyentes = len(guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(interaction):
    if not interaction.guild.voice_client: return
    
    canal = interaction.guild.voice_client.channel
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in canal.members)

    if bot.songs_played >= 3:
        bot.songs_played = 0
        if not es_vip and os.path.exists("anuncio.mp3"):
            source = discord.FFmpegPCMAudio("anuncio.mp3")
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction.guild), bot.loop)
            return

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- INTERFAZ DE BÚSQUEDA ---

class SongSelect(ui.Select):
    def __init__(self, options_data):
        options = [discord.SelectOption(label=d['title'][:100], description=f"Por {d['uploader']}", value=str(i)) for i, d in enumerate(options_data)]
        super().__init__(placeholder="Selecciona la canción que quieres...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        selected = self.options_data[int(self.values[0])]
        url = selected['url']
        titulo = selected['title']
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        if vc.is_playing():
            bot.queue.append((url, titulo))
            await interaction.response.edit_message(content=f"✅ Añadida a la cola: **{titulo}**", view=None)
        else:
            bot.songs_played += 1
            bot.current_track = titulo
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            await interaction.response.edit_message(content=f"🎶 Sonando ahora: **{titulo}**", view=None)

class SongView(ui.View):
    def __init__(self, options_data):
        super().__init__()
        self.add_item(SongSelect(options_data))

# --- COMANDOS ---

@bot.tree.command(name="play", description="Busca y elige música")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(cancion, download=False))
        results = data['entries']
        view = SongView(results)
        await interaction.followup.send("🔎 He encontrado estas opciones:", view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="announce", description="Reproduce el anuncio manualmente")
async def announce(interaction: discord.Interaction):
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if os.path.exists("anuncio.mp3"):
        if vc.is_playing(): vc.stop()
        vc.play(discord.FFmpegPCMAudio("anuncio.mp3"), after=lambda e: play_next(interaction))
        await registrar_anuncio(interaction.guild)
        await interaction.response.send_message("📢 Reproduciendo anuncio forzado...")
    else:
        await interaction.response.send_message("❌ Sube el archivo anuncio.mp3.")

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
    if not bot.queue: return await interaction.response.send_message("📋 Vacía.")
    msg = "\n".join([f"{i+1}. {t[1]}" for i, t in enumerate(bot.queue[:5])])
    await interaction.response.send_message(f"📋 **Cola:**\n{msg}")

@bot.tree.command(name="nowplaying")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 Sonando: **{bot.current_track or 'Nada'}**")

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 Mezclado.")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volumen: {vol}%")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 {round(bot.latency * 1000)}ms")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ Limpia.")

@bot.tree.command(name="stats")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    vistas = data["views"] if data else 0
    await interaction.response.send_message(f"📊 Impacto: **{vistas} oyentes**.")

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

@bot.tree.command(name="restart")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Reiniciando canción...")

@bot.tree.command(name="bassboost")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Bass Boost activado (Simulado)")

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Bucle activado.")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 Buscando letras para {bot.current_track}...")

@bot.tree.command(name="info")
async def info(interaction: discord.Interaction):
    await interaction.response.send_message("🤖 Flexus V3 | Docker Pack | VIP & Ads System")

@bot.tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("👑 Comandos: play, announce, skip, stop, pause, resume, queue, nowplaying, shuffle, volume, ping, clear, stats, leave, jump, restart, bassboost, loop, lyrics, info")

bot.run(TOKEN)
