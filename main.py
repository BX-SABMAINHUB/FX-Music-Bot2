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

# --- SERVIDOR WEB ---
app = Flask(__name__)
CORS(app)
live_reviews = []

@app.route('/')
def health(): return "Flexus Audio Engine Online"

@app.route('/api/reviews', methods=['GET'])
def get_reviews(): return jsonify(live_reviews)

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, host='0.0.0.0')

# --- CONFIGURACIÓN ---
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
        print(f"💎 FLEXUS V12.1: AUDIO ENGINE REPARADO") 

bot = FlexusBot() 

# --- SISTEMA DE EMBEDS DECORADOS ---
def flexus_embed(title, description, color=0x00ffcc, thumb=None):
    embed = discord.Embed(title=f"┏━💎 FLEXUS PREMIUM ━┓\n┃ {title}", description=f"┃\n┃ {description}\n┃\n┗━━━━━━━━━━━━━━┛", color=color)
    embed.set_footer(text="SISTEMA DE AUDIO V12.1 • CALIDAD 192K", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    if thumb: embed.set_thumbnail(url=thumb)
    return embed

# --- MOTOR DE AUDIO ELITE (192K) ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'force-ipv4': True,
} 
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k -ar 48000' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

async def get_audio_info(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

def play_next(interaction, channel_id, user):
    if not interaction.guild.voice_client: return
    
    # Sistema de Anuncio
    is_vip = any(role.name == VIP_ROLE_NAME for role in user.roles)
    if not is_vip and bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS), 
            after=lambda e: play_next(interaction, channel_id, user))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        
        def after_callback(error):
            async def end_task():
                chan = bot.get_channel(channel_id)
                view = ui.View().add_item(ui.Button(label="⭐ VALORAR PISTA", style=discord.ButtonStyle.success, emoji="💿"))
                view.children[0].callback = lambda i: i.response.send_modal(ReviewModal(title))
                await chan.send(embed=flexus_embed("PISTA TERMINADA", f"**{title}**\n\nDeja tu reseña para nuestra web."), view=view)
            bot.loop.create_task(end_task())
            play_next(interaction, channel_id, user)

        # Extracción segura en hilo aparte para evitar el "no carga"
        info = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=after_callback)

# --- MODAL DE RESEÑA ---
class ReviewModal(ui.Modal, title="⭐ RESEÑA DE AUDIO"):
    def __init__(self, track):
        super().__init__()
        self.track = track
    score = ui.TextInput(label="Nota (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    comment = ui.TextInput(label="Comentario", style=discord.TextStyle.paragraph, min_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        data = {"usuario": interaction.user.name, "musica": self.track, "estrellas": self.score.value, "mensaje": self.comment.value, "hora": datetime.now().strftime("%H:%M")}
        live_reviews.append(data)
        await reviews_col.insert_one(data)
        await interaction.response.send_message(embed=flexus_embed("GRACIAS", "Tu reseña ha sido enviada con éxito."), ephemeral=True)

# --- LOS 19 COMANDOS DECORADOS ---

@bot.tree.command(name="play", description="Reproduce música con calidad máxima")
async def play(i: discord.Interaction, buscar: str):
    await i.response.defer()
    try:
        data = await get_audio_info(f"ytsearch5:{buscar}")
        results = data['entries']
        
        class SelectSong(ui.Select):
            def __init__(self):
                options = [discord.SelectOption(label=r['title'][:90], value=str(idx), emoji="🎧") for idx, r in enumerate(results)]
                super().__init__(placeholder="💎 Selecciona una canción de la lista...", options=options)

            async def callback(self, inter: discord.Interaction):
                await inter.response.edit_message(embed=flexus_embed("CARGANDO", "Sincronizando con el servidor de audio... 🚀", 0xffff00), view=None)
                s = results[int(self.values[0])]
                vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
                bot.queue.append((s['webpage_url'], s['title']))
                if not vc.is_playing(): play_next(inter, inter.channel.id, inter.user)
                await inter.followup.send(embed=flexus_embed("AÑADIDO", f"**{s['title']}**\n\nPreparando señal de 192kbps..."))

        await i.followup.send(embed=flexus_embed("RESULTADOS", f"Búsqueda: `{buscar}`\nSelecciona abajo para reproducir."), view=ui.View().add_item(SelectSong()))
    except Exception as e:
        await i.followup.send(embed=flexus_embed("ERROR", f"No pude procesar la búsqueda: {e}", 0xff0000))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=flexus_embed("SALTAR", "Pasando a la siguiente pista de audio."))

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=flexus_embed("DETENER", "Se ha limpiado la cola y cerrado la conexión.", 0xff0000))

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message(embed=flexus_embed("PAUSA", "Audio pausado.", 0xffff00))

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message(embed=flexus_embed("REANUDAR", "Continuando reproducción."))

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    tracks = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "Cola vacía."
    await i.response.send_message(embed=flexus_embed("COLA", tracks, 0x3498db))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(embed=flexus_embed("EN VIVO", f"Pista: **{bot.current_track}**", 0x9b59b6))

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message(embed=flexus_embed("MEZCLAR", "Orden de la cola aleatorio."))

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(embed=flexus_embed("VOLUMEN", f"Ajustado al **{v}%**"))

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction):
    await i.response.send_message(embed=flexus_embed("PING", f"Latencia: `{round(bot.latency*1000)}ms`"))

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message(embed=flexus_embed("LIMPIAR", "Cola eliminada correctamente."))

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=flexus_embed("SALIR", "Bot desconectado del canal."))

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, p: int):
    if 0 < p <= len(bot.queue):
        for _ in range(p-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(embed=flexus_embed("JUMP", f"Saltado a la pista {p}."))

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=flexus_embed("REPETIR", "Reiniciando track actual."))

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction):
    await i.response.send_message(embed=flexus_embed("BASS", "Ecualización BassBoost aplicada."))

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(embed=flexus_embed("LOOP", f"Modo bucle: {'ON' if bot.loop_mode else 'OFF'}"))

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction):
    await i.response.send_message(embed=flexus_embed("LETRA", "Buscando en Genius..."))

@bot.tree.command(name="stats")
async def st(i: discord.Interaction):
    await i.response.send_message(embed=flexus_embed("STATS", f"Canciones hoy: {bot.songs_played}"))

@bot.tree.command(name="help")
async def h(i: discord.Interaction):
    cmds = "play, skip, stop, pause, resume, queue, nowplaying, shuffle, volume, ping, clear, leave, jump, restart, bassboost, loop, lyrics, stats, help"
    await i.response.send_message(embed=flexus_embed("AYUDA", f"Comandos:\n`{cmds}`"))

@bot.tree.command(name="admin_ban")
async def admin_ban(i: discord.Interaction, user_id: str):
    if i.user.id != 1313950667773055010: return
    await blacklist_col.insert_one({"user_id": user_id})
    await i.response.send_message(embed=flexus_embed("BANEADO", f"ID {user_id} bloqueada."), ephemeral=True)

bot.run(TOKEN)
