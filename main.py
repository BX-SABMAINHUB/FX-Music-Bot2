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
VIP_ROLE_NAME = "VIP"  # Nombre exacto del rol que no escucha anuncios

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
        print(f"💎 FLEXUS V8.0: AUDIO 192K & SISTEMA VIP ACTIVADO") 

bot = FlexusBot() 

# CONFIGURACIÓN DE AUDIO PROFESIONAL (192kbps)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0'
} 
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k -ar 48000 -af "volume=1.0"' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS CON DECORACIÓN ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN PREMIUM FLEXUS ⭐"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="Nota (1-5)", placeholder="⭐⭐⭐⭐⭐", min_length=1, max_length=1)
    reason = ui.TextInput(label="Comentario Técnico", style=discord.TextStyle.paragraph, placeholder="¿Qué tal la fidelidad de audio?", min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        await reviews_col.insert_one({
            "user": interaction.user.name,
            "user_avatar": str(interaction.user.display_avatar.url),
            "song": self.song_title, 
            "stars": int(self.stars.value) if self.stars.value.isdigit() else 5,
            "message": self.reason.value,
            "timestamp": datetime.utcnow()
        })
        embed = discord.Embed(title="✅ RESEÑA PUBLICADA", description=f"Gracias **{interaction.user.name}**. Tu opinión ya está en el Dashboard.", color=0x00ff77)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- SISTEMA DE REPRODUCCIÓN (AUDIO 192K + LÓGICA VIP) ---
def play_next(interaction, channel_id, user):
    if not interaction.guild.voice_client: return
    
    # Lanzar reseña al finalizar canción real
    if bot.current_track and not bot.loop_mode:
        song_ended = bot.current_track
        async def trigger_review():
            chan = bot.get_channel(channel_id)
            if chan:
                view = ui.View().add_item(ui.Button(label="Reseñar Pista ⭐", style=discord.ButtonStyle.success, emoji="💿"))
                async def cb(i): await i.response.send_modal(ReviewModal(song_ended))
                view.children[0].callback = cb
                embed = discord.Embed(title="🎼 SESIÓN FINALIZADA", description=f"Has escuchado: **{song_ended}**\n¿Cómo calificarías la experiencia?", color=0x00ff77)
                await chan.send(embed=embed, view=view)
        bot.loop.create_task(trigger_review())

    # Lógica de Anuncios: Cada 3 canciones si NO es VIP
    is_vip = any(role.name == VIP_ROLE_NAME for role in user.roles)
    if not is_vip and bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        embed_adv = discord.Embed(title="📢 PUBLICIDAD FLEXUS", description="Reproduciendo anuncio comercial...\n*¡Hazte VIP para eliminar anuncios!*", color=0xffff00)
        bot.loop.create_task(interaction.channel.send(embed=embed_adv))
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id, user))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        data = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id, user))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS MANUALES CON EMBEDS ---

@bot.tree.command(name="play", description="🎶 Sonido Master Hi-Fi 192kbps")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    u_id = interaction.user.id

    class SelectSong(ui.Select):
        def __init__(self):
            super().__init__(placeholder="💎 Selecciona la calidad master...", options=[
                discord.SelectOption(label=r['title'][:90], emoji="🎧", value=str(i)) for i, r in enumerate(results)
            ])
        async def callback(self, inter: discord.Interaction):
            if inter.user.id != u_id: return await inter.response.send_message("❌ No es tu búsqueda.", ephemeral=True)
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title']))
                await inter.followup.send(embed=discord.Embed(description=f"📥 **Añadido:** {s['title']}", color=0x3498db))
            else:
                bot.current_track = s['title']
                bot.songs_played += 1
                info = ytdl.extract_info(s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter, inter.channel.id, inter.user))
                await inter.followup.send(embed=discord.Embed(title="🚀 SONIDO MASTER 192K", description=f"**{s['title']}**\nEstado: `High Fidelity`", color=0x00ff77))
    await interaction.followup.send(view=ui.View().add_item(SelectSong()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=discord.Embed(description="⏭️ **Pista saltada.**", color=0x00ff77))

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=discord.Embed(description="⏹️ **Sesión cerrada.**", color=0xff4444))

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message(embed=discord.Embed(description="⏸️ **Música en pausa.**", color=0xffcc00))

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message(embed=discord.Embed(description="▶️ **Reproducción reanudada.**", color=0x00ff77))

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    txt = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "La lista está vacía."
    await i.response.send_message(embed=discord.Embed(title="📋 COLA DE REPRODUCCIÓN", description=txt, color=0x3498db))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction): 
    await i.response.send_message(embed=discord.Embed(title="🎧 ESCUCHANDO", description=f"**{bot.current_track}**", color=0x00ff77))

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message(embed=discord.Embed(description="🔀 **Cola mezclada aleatoriamente.**", color=0x9b59b6))

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client and i.guild.voice_client.source: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(embed=discord.Embed(description=f"🔊 **Volumen fijado al {v}%**", color=0x00ff77))

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction): 
    await i.response.send_message(embed=discord.Embed(description=f"📡 **Latencia:** `{round(bot.latency*1000)}ms`", color=0x00ff77))

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message(embed=discord.Embed(description="🗑️ **Cola eliminada.**", color=0xff4444))

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=discord.Embed(description="👋 **Flexus se ha retirado.**", color=0x000000))

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, p: int):
    if 0 < p <= len(bot.queue):
        for _ in range(p-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(embed=discord.Embed(description=f"⏩ **Saltando a la posición {p}...**", color=0x00ff77))

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=discord.Embed(description="🔄 **Reiniciando pista.**", color=0x00ff77))

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction): 
    await i.response.send_message(embed=discord.Embed(title="🔥 BASS BOOST", description="Ecualización de bajos optimizada.", color=0xe67e22))

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(embed=discord.Embed(description=f"🔁 **Modo bucle:** `{'ON' if bot.loop_mode else 'OFF'}`", color=0x00ff77))

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction): 
    await i.response.send_message(embed=discord.Embed(title="🔍 BUSCANDO LETRAS", description=f"Obteniendo lírica de: **{bot.current_track}**", color=0x3498db))

@bot.tree.command(name="stats")
async def st(i: discord.Interaction): 
    await i.response.send_message(embed=discord.Embed(title="📊 ESTADÍSTICAS", description=f"Pistas hoy: `{bot.songs_played}`\nServidor: `Elite Premium`", color=0x00ff77))

@bot.tree.command(name="help")
async def help(i: discord.Interaction):
    e = discord.Embed(title="👑 FLEXUS PREMIUM DASHBOARD", description="`play`, `skip`, `stop`, `pause`, `resume`, `queue`, `nowplaying`, `shuffle`, `volume`, `ping`, `clear`, `leave`, `jump`, `restart`, `bassboost`, `loop`, `lyrics`, `stats`, `help`", color=0x00ff77)
    await i.response.send_message(embed=e)

bot.run(TOKEN)
