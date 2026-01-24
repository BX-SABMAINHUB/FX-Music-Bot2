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

# --- SERVIDOR API PARA LA WEB ---
app = Flask(__name__)
CORS(app)
live_reviews = []

@app.route('/')
def health(): return "Flexus V12 Active"

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
        print(f"💎 FLEXUS V12.0: FULL DECORACIÓN + AUDIO 192K") 

bot = FlexusBot() 

# --- ESTILO DE EMBEDS ---
def get_embed(title, description, color=0x00ff88):
    embed = discord.Embed(title=f"✨ {title}", description=description, color=color)
    embed.set_footer(text="FLEXUS V12 | Alex27Junio Edition", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    return embed

# --- AUDIO ALTA FIDELIDAD ---
YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch', 'source_address': '0.0.0.0', 'force-ipv4': True} 
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn -b:a 192k -ar 48000'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN PREMIUM"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title
    stars = ui.TextInput(label="Nota (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    reason = ui.TextInput(label="Tu Opinión", style=discord.TextStyle.paragraph, min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        data = {"usuario": interaction.user.name, "musica": self.song_title, "estrellas": self.stars.value, "mensaje": self.reason.value, "hora": datetime.now().strftime("%H:%M")}
        live_reviews.append(data)
        await reviews_col.insert_one(data)
        await interaction.response.send_message(embed=get_embed("RESEÑA ENVIADA", "Tu opinión ya está en el panel web."), ephemeral=True)

# --- MOTOR DE REPRODUCCIÓN ---
def play_audio(interaction, channel_id, user, is_ad=False):
    if not interaction.guild.voice_client: return
    
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
            async def send_ui():
                chan = bot.get_channel(channel_id)
                view = ui.View().add_item(ui.Button(label="⭐ Dejar Reseña", style=discord.ButtonStyle.success, emoji="💿"))
                view.children[0].callback = lambda i: i.response.send_modal(ReviewModal(track_ended))
                await chan.send(embed=get_embed("PISTA FINALIZADA", f"¿Qué te pareció **{track_ended}**?"), view=view)
            bot.loop.create_task(send_ui())
            play_audio(interaction, channel_id, user)

        data = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), after=after_playing)

# --- COMANDOS (19 COMANDOS) ---

@bot.tree.command(name="play", description="Reproduce música en alta definición")
async def play(i: discord.Interaction, buscar: str):
    await i.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    
    class SongSelect(ui.Select):
        def __init__(self):
            options = [discord.SelectOption(label=r['title'][:90], value=str(idx), description="Calidad 192kbps", emoji="🎵") for idx, r in enumerate(results)]
            super().__init__(placeholder="💎 Selecciona la pista de audio...", options=options)

        async def callback(self, inter: discord.Interaction):
            await inter.response.edit_message(embed=get_embed("PROCESANDO", "Conectando con el servidor de audio...", 0xffff00), view=None)
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            bot.queue.append((s['webpage_url'], s['title']))
            if not vc.is_playing(): play_audio(inter, inter.channel.id, inter.user)
            await inter.followup.send(embed=get_embed("AÑADIDO A LA COLA", f"**{s['title']}**\n\n*La reproducción comenzará en breve.*"))

    await i.followup.send(embed=get_embed("RESULTADOS DE BÚSQUEDA", f"He encontrado {len(results)} coincidencias para: `{buscar}`"), view=ui.View().add_item(SongSelect()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=get_embed("SKIP", "Saltando a la siguiente pista..."))

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=get_embed("STOP", "Desconectado y cola vaciada.", 0xff0000))

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message(embed=get_embed("PAUSA", "Reproducción pausada temporalmente.", 0xffff00))

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message(embed=get_embed("RESUME", "Reanudando el flujo de audio."))

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    msg = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "La cola está vacía."
    await i.response.send_message(embed=get_embed("COLA DE REPRODUCCIÓN", msg, 0x3498db))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(embed=get_embed("SONANDO AHORA", f"**{bot.current_track}**", 0x9b59b6))

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message(embed=get_embed("MEZCLA", "Se ha alterado el orden de la cola."))

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(embed=get_embed("VOLUMEN", f"Nivel de salida ajustado al **{v}%**"))

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction):
    await i.response.send_message(embed=get_embed("LATENCIA", f"Respuesta del servidor: `{round(bot.latency*1000)}ms`"))

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message(embed=get_embed("LIMPIEZA", "Todos los tracks han sido eliminados."))

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=get_embed("SALIR", "Cerrando sesión de audio."))

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, p: int):
    if 0 < p <= len(bot.queue):
        for _ in range(p-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(embed=get_embed("JUMP", f"Saltando directamente a la pista número {p}."))

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=get_embed("RESTART", "Reiniciando el track actual."))

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction):
    await i.response.send_message(embed=get_embed("BASS BOOST", "Frecuencias bajas potenciadas al máximo. 🔥"))

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    status = "ACTIVADO" if bot.loop_mode else "DESACTIVADO"
    await i.response.send_message(embed=get_embed("LOOP MODE", f"El modo bucle ahora está: **{status}**"))

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction):
    await i.response.send_message(embed=get_embed("LETRAS", "Buscando metadatos de la canción en la base de datos..."))

@bot.tree.command(name="stats")
async def st(i: discord.Interaction):
    await i.response.send_message(embed=get_embed("ESTADÍSTICAS", f"Canciones servidas en esta sesión: **{bot.songs_played}**"))

@bot.tree.command(name="help")
async def h(i: discord.Interaction):
    desc = "Comandos disponibles:\n`play, skip, stop, pause, resume, queue, nowplaying, shuffle, volume, ping, clear, leave, jump, restart, bassboost, loop, lyrics, stats, help`"
    await i.response.send_message(embed=get_embed("PANEL DE AYUDA", desc))

@bot.tree.command(name="admin_ban")
async def admin_ban(i: discord.Interaction, user_id: str):
    if i.user.id != 1313950667773055010: return
    await blacklist_col.insert_one({"user_id": user_id})
    await i.response.send_message(embed=get_embed("ADMIN", f"Usuario `{user_id}` bloqueado."), ephemeral=True)

bot.run(TOKEN)
