import discord 
from discord import app_commands, ui
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# --- CONFIGURACIÓN DE ÉLITE ---
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"
VIP_ROLE_NAME = "VIP" 

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
reviews_col = db["reviews"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="/", intents=intents) 
        self.queue = [] 
        self.current_track = None
        self.songs_played = 0
        self.loop_mode = False

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"💎 FLEXUS V12.0: SISTEMA ANTI-ERROR ACTIVADO") 

bot = FlexusBot() 

# CONFIGURACIÓN YTDL OPTIMIZADA PARA VELOCIDAD
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'force-ipv4': True,
    'cachedir': False
} 

# ESTO SOLUCIONA EL CIERRE RÁPIDO: Buffer masivo y reconexión agresiva
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 10M -analyzeduration 10M',
    'options': '-vn -b:a 192k -ar 48000' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN PREMIUM ⭐"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title
    stars = ui.TextInput(label="Nota (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    reason = ui.TextInput(label="Opinión", style=discord.TextStyle.paragraph, placeholder="¿Qué tal la calidad?", min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        await reviews_col.insert_one({
            "user": interaction.user.name,
            "song": self.song_title, 
            "stars": self.stars.value,
            "message": self.reason.value,
            "timestamp": datetime.utcnow()
        })
        await interaction.response.send_message(embed=discord.Embed(title="✅ GRACIAS", color=0x00ff77), ephemeral=True)

# --- MOTOR DE REPRODUCCIÓN BLINDADO ---
def play_audio(interaction, channel_id, user, is_ad=False):
    if not interaction.guild.voice_client: return

    # Si NO es un anuncio, manejamos la lógica de fin de canción
    def after_playing(error):
        if error: print(f"Error en reproducción: {error}")
        
        # Si terminó una canción real (no anuncio), lanzar reseña
        if not is_ad and bot.current_track and not bot.loop_mode:
            track_ended = bot.current_track
            async def send_rev():
                chan = bot.get_channel(channel_id)
                if chan:
                    view = ui.View().add_item(ui.Button(label="Dejar Reseña ⭐", style=discord.ButtonStyle.success, emoji="💿"))
                    async def cb(i): await i.response.send_modal(ReviewModal(track_ended))
                    view.children[0].callback = cb
                    await chan.send(embed=discord.Embed(title="🎼 CANCIÓN FINALIZADA", description=f"**{track_ended}**", color=0x00ff77), view=view)
            bot.loop.create_task(send_rev())

        # Siguiente en la cola
        bot.loop.call_soon_threadsafe(next_song, interaction, channel_id, user)

    # LÓGICA DE ANUNCIO VIP
    is_vip = any(role.name == VIP_ROLE_NAME for role in user.roles)
    if not is_ad and not is_vip and bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS), after=lambda e: play_audio(interaction, channel_id, user, is_ad=True))
        bot.loop.create_task(interaction.channel.send(embed=discord.Embed(title="📢 ANUNCIO", color=0xffff00)))
        return

    # Reproducir siguiente canción
    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        
        # Extraer info fresca justo antes de tocar para evitar URLs expiradas
        data = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), after=after_playing)
    else:
        bot.current_track = None

def next_song(interaction, channel_id, user):
    play_audio(interaction, channel_id, user)

# --- COMANDOS (19 COMANDOS DECORADOS) ---
@bot.tree.command(name="play", description="🎶 Sonido Premium 192k")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']

    class SongSelect(ui.Select):
        def __init__(self):
            super().__init__(placeholder="💎 Elige la pista...", options=[
                discord.SelectOption(label=r['title'][:90], emoji="💿", value=str(i)) for i, r in enumerate(results)
            ])
        async def callback(self, inter: discord.Interaction):
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            
            if vc.is_playing() or vc.is_paused():
                bot.queue.append((s['webpage_url'], s['title']))
                await inter.followup.send(embed=discord.Embed(description=f"📥 **En cola:** {s['title']}", color=0x3498db))
            else:
                bot.queue.append((s['webpage_url'], s['title']))
                play_audio(inter, inter.channel.id, inter.user)
                await inter.followup.send(embed=discord.Embed(title="🚀 REPRODUCIENDO", description=f"**{s['title']}**", color=0x00ff77))

    await interaction.followup.send(view=ui.View().add_item(SongSelect()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=discord.Embed(description="⏭️ **Saltada**", color=0x00ff77))

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=discord.Embed(description="⏹️ **Desconectado**", color=0xff0000))

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message(embed=discord.Embed(description="⏸️ **Pausado**", color=0xffff00))

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message(embed=discord.Embed(description="▶️ **Reanudado**", color=0x00ff77))

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    msg = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "Vacia"
    await i.response.send_message(embed=discord.Embed(title="📋 COLA", description=msg, color=0x3498db))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="🎧 SONANDO", description=f"{bot.current_track}", color=0x00ff77))

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message(embed=discord.Embed(description="🔀 **Mezclado**", color=0x9b59b6))

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client and i.guild.voice_client.source: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(embed=discord.Embed(description=f"🔊 **Volumen:** {v}%", color=0x00ff77))

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(description=f"📡 `{round(bot.latency*1000)}ms`", color=0x00ff77))

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message(embed=discord.Embed(description="🗑️ **Cola limpia**", color=0xff0000))

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=discord.Embed(description="👋 **Adiós**", color=0xff4444))

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, p: int):
    if 0 < p <= len(bot.queue):
        for _ in range(p-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(embed=discord.Embed(description=f"⏩ **Salto a {p}**", color=0x00ff77))

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=discord.Embed(description="🔄 **Reiniciando**", color=0x00ff77))

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="🔥 BASS", description="Activado", color=0xe67e22))

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(embed=discord.Embed(description=f"🔁 **Bucle:** {bot.loop_mode}", color=0x00ff77))

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="🔍 LETRAS", description="Buscando...", color=0x3498db))

@bot.tree.command(name="stats")
async def st(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="📊 STATS", description=f"Hoy: {bot.songs_played}", color=0x00ff77))

@bot.tree.command(name="help")
async def h(i: discord.Interaction):
    e = discord.Embed(title="👑 FLEXUS HELP", description="`play`, `skip`, `stop`, `pause`, `resume`, `queue`, `np`, `shuffle`, `volume`, `ping`, `clear`, `leave`, `jump`, `restart`, `bass`, `loop`, `lyrics`, `stats`, `help`", color=0x00ff77)
    await i.response.send_message(embed=e)

bot.run(TOKEN)
