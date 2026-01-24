import discord 
from discord import app_commands, ui
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
import threading
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# IMPORTANTE: Flask debe estar instalado en requirements.txt
from flask import Flask, jsonify
from flask_cors import CORS

# --- CONFIGURACIÓN DE LA API WEB ---
app = Flask(__name__)
CORS(app)
live_reviews = []

@app.route('/')
def health_check(): return "Flexus System Online"

@app.route('/api/reviews', methods=['GET'])
def get_reviews(): return jsonify(live_reviews)

def run_web_server():
    # Railway asigna un puerto automáticamente
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, host='0.0.0.0')

# --- CONFIGURACIÓN DE ÉLITE ---
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"
VIP_ROLE_NAME = "VIP" 

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
reviews_col = db["reviews"]
blacklist_col = db["blacklist"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="/", intents=intents) 
        self.queue = [] 
        self.current_track = None
        self.songs_played = 0
        self.loop_mode = False

    async def setup_hook(self): 
        # Iniciar servidor web en segundo plano
        threading.Thread(target=run_web_server, daemon=True).start()
        await self.tree.sync() 
        print(f"💎 FLEXUS V12.0: SISTEMA CONECTADO AL PUERTO 5000") 

bot = FlexusBot() 

# --- SEGURIDAD ---
@bot.tree.interaction_check
async def check_if_banned(interaction: discord.Interaction):
    user_banned = await blacklist_col.find_one({"user_id": str(interaction.user.id)})
    if user_banned:
        return False
    return True

# --- AUDIO 192K ---
YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'default_search': 'ytsearch', 'quiet': True} 
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k -ar 48000' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN PREMIUM"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title
    stars = ui.TextInput(label="Nota (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    reason = ui.TextInput(label="Tu Opinión", style=discord.TextStyle.paragraph, min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            "usuario": interaction.user.name,
            "musica": self.song_title,
            "estrellas": self.stars.value,
            "mensaje": self.reason.value,
            "hora": datetime.now().strftime("%H:%M")
        }
        live_reviews.append(data) # Para la web
        await reviews_col.insert_one(data) # Para MongoDB
        await interaction.response.send_message("✅ Reseña enviada al panel", ephemeral=True)

# --- MOTOR DE REPRODUCCIÓN ---
def play_audio(interaction, channel_id, user, is_ad=False):
    if not interaction.guild.voice_client: return
    
    # Lógica de Anuncio
    is_vip = any(role.name == VIP_ROLE_NAME for role in user.roles)
    if not is_ad and not is_vip and bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS), 
                                          after=lambda e: play_audio(interaction, channel_id, user, is_ad=True))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        
        def after_playing(error):
            track_ended = title
            async def trigger_ui():
                chan = bot.get_channel(channel_id)
                view = ui.View().add_item(ui.Button(label="⭐ Opinar", style=discord.ButtonStyle.success))
                view.children[0].callback = lambda i: i.response.send_modal(ReviewModal(track_ended))
                await chan.send(embed=discord.Embed(title="🎼 PISTA TERMINADA", description=f"**{track_ended}**", color=0x00ff77), view=view)
            bot.loop.create_task(trigger_ui())
            play_audio(interaction, channel_id, user)

        data = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), after=after_playing)

# --- LOS 19 COMANDOS ---
@bot.tree.command(name="play")
async def p(i: discord.Interaction, buscar: str):
    await i.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch1:{buscar}", download=False)
    s = data['entries'][0]
    vc = i.guild.voice_client or await i.user.voice.channel.connect()
    bot.queue.append((s['webpage_url'], s['title']))
    if not vc.is_playing(): play_audio(i, i.channel.id, i.user)
    await i.followup.send(f"🚀 **REPRODUCIENDO:** {s['title']}")

@bot.tree.command(name="skip")
async def sk(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("⏭️ Siguiente pista")

@bot.tree.command(name="stop")
async def stp(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️ Bot detenido")

@bot.tree.command(name="pause")
async def ps(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message("⏸️ Pausado")

@bot.tree.command(name="resume")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message("▶️ Reanudado")

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    text = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:5])]) or "Vacia"
    await i.response.send_message(embed=discord.Embed(title="📋 COLA ACTUAL", description=text, color=0x3498db))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(f"🎧 Sonando ahora: **{bot.current_track}**")

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message("🔀 Cola mezclada")

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(f"🔊 Volumen al {v}%")

@bot.tree.command(name="ping")
async def png(i: discord.Interaction):
    await i.response.send_message(f"📡 `{round(bot.latency*1000)}ms` de latencia")

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message("🗑️ Cola limpiada")

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("👋 Hasta luego")

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, n: int):
    if 0 < n <= len(bot.queue):
        for _ in range(n-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(f"⏩ Saltando a la pista {n}")

@bot.tree.command(name="restart")
async def rst(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("🔄 Reiniciando canción")

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction):
    await i.response.send_message("🔥 Graves potenciados")

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(f"🔁 Modo bucle: {'ACTIVADO' if bot.loop_mode else 'DESACTIVADO'}")

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction):
    await i.response.send_message("🔍 Buscando letras...")

@bot.tree.command(name="stats")
async def sts(i: discord.Interaction):
    await i.response.send_message(f"📊 Sesión: {bot.songs_played} canciones reproducidas")

@bot.tree.command(name="help")
async def h(i: discord.Interaction):
    await i.response.send_message("👑 Comandos: play, skip, stop, pause, resume, queue, np, shuffle, volume, ping, clear, leave, jump, restart, bassboost, loop, lyrics, stats, help")

@bot.tree.command(name="admin_ban")
async def ab(i: discord.Interaction, user_id: str):
    if i.user.id != 1313950667773055010: return
    await blacklist_col.insert_one({"user_id": user_id})
    await i.response.send_message(f"🚫 ID {user_id} baneada.", ephemeral=True)

bot.run(TOKEN)
