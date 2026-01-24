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
from flask import Flask, jsonify
from flask_cors import CORS

# --- SERVIDOR API WEB ---
app = Flask(__name__)
CORS(app)
live_reviews = []

@app.route('/')
def health(): return "FLEXUS CORE ONLINE"

@app.route('/api/reviews', methods=['GET'])
def get_reviews(): return jsonify(live_reviews)

def run_web_server():
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
        threading.Thread(target=run_web_server, daemon=True).start()
        await self.tree.sync() 
        print(f"💎 FLEXUS V12.2: AUDIO ENGINE Y DECORACIÓN ACTIVADOS") 

bot = FlexusBot() 

# --- SISTEMA DE DISEÑO (FRAMES) ---
def flex_frame(title, desc, color=0x00ffcc, icon="🎧"):
    embed = discord.Embed(
        title=f"┏━━━━━━━━━━━━━━━━━┓\n┃ {icon} {title}\n┗━━━━━━━━━━━━━━━━━┛",
        description=f"```\n{desc}\n```",
        color=color,
        timestamp=datetime.now()
    )
    embed.set_footer(text="FLEXUS PREMIUM • V12.2 • CALIDAD 192K", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    return embed

# --- MOTOR DE AUDIO (CALIDAD 192K) ---
YTDL_OPTS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch', 'source_address': '0.0.0.0', 'force-ipv4': True} 
FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn -b:a 192k -ar 48000'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

def play_engine(interaction, channel_id, user, is_ad=False):
    if not interaction.guild.voice_client: return
    
    # Sistema de Anuncios
    is_vip = any(r.name == VIP_ROLE_NAME for r in user.roles)
    if not is_ad and not is_vip and bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTS), after=lambda e: play_engine(interaction, channel_id, user, is_ad=True))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        
        def after_callback(error):
            async def end_task():
                chan = bot.get_channel(channel_id)
                view = ui.View().add_item(ui.Button(label="RESEÑA WEB ⭐", style=discord.ButtonStyle.success, emoji="💿"))
                view.children[0].callback = lambda i: i.response.send_modal(ReviewModal(title))
                await chan.send(embed=flex_frame("PISTA TERMINADA", f"TRACK: {title}\nDeja tu valoración para la web.", 0x00ff77), view=view)
            bot.loop.create_task(end_task())
            play_engine(interaction, channel_id, user)

        data = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTS), after=after_callback)

# --- MODAL RESEÑA ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN WEB"):
    def __init__(self, track): super().__init__(); self.track = track
    stars = ui.TextInput(label="Nota (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    msg = ui.TextInput(label="Comentario", style=discord.TextStyle.paragraph, min_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        data = {"usuario": interaction.user.name, "musica": self.track, "estrellas": self.stars.value, "mensaje": self.msg.value, "hora": datetime.now().strftime("%H:%M")}
        live_reviews.append(data); await reviews_col.insert_one(data)
        await interaction.response.send_message(embed=flex_frame("EXITO", "Tu reseña se ha enviado al panel de Alex.", 0x00ffcc), ephemeral=True)

# --- LOS 19 COMANDOS ---
@bot.tree.command(name="play", description="Audio 192k con Frame Decorado")
async def play(i: discord.Interaction, buscar: str):
    await i.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{buscar}", download=False))
    results = data['entries']
    
    class SongSelect(ui.Select):
        def __init__(self):
            opts = [discord.SelectOption(label=r['title'][:90], value=str(idx), emoji="📀") for idx, r in enumerate(results)]
            super().__init__(placeholder="💎 Elige la pista de audio...", options=opts)

        async def callback(self, inter: discord.Interaction):
            # FIX: Editamos el mensaje original para que no se quede "congelado"
            await inter.response.edit_message(embed=flex_frame("CARGANDO", "Iniciando Motor de Audio Flexus...", 0xffff00, "🚀"), view=None)
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            bot.queue.append((s['webpage_url'], s['title']))
            if not vc.is_playing(): play_engine(inter, inter.channel.id, inter.user)
            await inter.followup.send(embed=flex_frame("AÑADIDO", f"TRACK: {s['title']}\nESTADO: En Cola / Reproduciendo", 0x00ff77))

    await i.followup.send(embed=flex_frame("BUSQUEDA", f"Resultados para: {buscar}\nSelecciona abajo:", 0x3498db, "🔍"), view=ui.View().add_item(SongSelect()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=flex_frame("SKIP", "Saltando a la siguiente pista...", 0x00ffcc, "⏭️"))

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=flex_frame("STOP", "Sistema apagado y cola limpia.", 0xff0000, "⏹️"))

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message(embed=flex_frame("PAUSE", "Audio pausado.", 0xffff00, "⏸️"))

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message(embed=flex_frame("RESUME", "Audio reanudado.", 0x00ffcc, "▶️"))

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    tracks = "\n".join([f"[{idx+1}] {t[1][:30]}..." for idx, t in enumerate(bot.queue[:10])]) or "LISTA VACÍA"
    await i.response.send_message(embed=flex_frame("COLA", tracks, 0x3498db, "📋"))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("SONANDO", f"ACTUAL: {bot.current_track}", 0x9b59b6, "🎧"))

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message(embed=flex_frame("MIX", "Orden de la lista aleatorio.", 0x9b59b6, "🔀"))

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(embed=flex_frame("VOLUMEN", f"Nivel: {v}%", 0x00ffcc, "🔊"))

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("PONG", f"Latencia: {round(bot.latency*1000)}ms", 0x00ffcc, "📡"))

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message(embed=flex_frame("CLEAR", "Cola vaciada con éxito.", 0xff0000, "🗑️"))

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=flex_frame("BYE", "Desconectado del canal.", 0xff0000, "👋"))

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, p: int):
    if 0 < p <= len(bot.queue):
        for _ in range(p-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(embed=flex_frame("JUMP", f"Saltado a la pista {p}.", 0x00ffcc, "⏩"))

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=flex_frame("RESTART", "Reiniciando track actual.", 0x00ffcc, "🔄"))

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("BASS", "Frecuencias bajas potenciadas.", 0xe67e22, "🔥"))

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(embed=flex_frame("LOOP", f"Bucle: {'ON' if bot.loop_mode else 'OFF'}", 0x00ffcc, "🔁"))

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("LYRICS", "Buscando metadatos de la letra...", 0x3498db, "🔍"))

@bot.tree.command(name="stats")
async def st(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("STATS", f"Tracks servidos: {bot.songs_played}", 0x00ffcc, "📊"))

@bot.tree.command(name="help")
async def h(i: discord.Interaction):
    cmds = "play, skip, stop, pause, resume, queue, np, shuffle, volume, ping, clear, leave, jump, restart, bassboost, loop, lyrics, stats, help"
    await i.response.send_message(embed=flex_frame("HELP", f"LISTA:\n{cmds}", 0x00ffcc, "👑"))

@bot.tree.command(name="admin_ban")
async def ab(i: discord.Interaction, user_id: str):
    if i.user.id != 1313950667773055010: return
    await blacklist_col.insert_one({"user_id": user_id})
    await i.response.send_message(embed=flex_frame("ADMIN", f"ID {user_id} bloqueada.", 0xff0000, "🚫"), ephemeral=True)

bot.run(TOKEN)
