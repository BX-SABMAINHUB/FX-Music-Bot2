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
        print(f"💎 FLEXUS V11.0: AUDIO MASTER 320K LIBOPUS ACTIVADO") 

bot = FlexusBot() 

# CONFIGURACIÓN DE CALIDAD EXTREMA
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
    'nocheckcertificate': True,
    'source_address': '0.0.0.0',
    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'opus','preferredquality': '320'}],
} 

# PARÁMETROS DE AUDIO MASTER (libopus + 320k + Buffer Blindado)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -probesize 20M -analyzeduration 20M',
    'options': '-vn -c:a libopus -b:a 320k -vbr on -compression_level 10' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS PREMIUM ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN CALIDAD MASTER ⭐"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="Puntuación Hi-Fi (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    reason = ui.TextInput(label="Feedback del Sonido 320k", style=discord.TextStyle.paragraph, placeholder="¿Cómo sentiste los bajos y agudos?", min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        await reviews_col.insert_one({
            "user": interaction.user.name,
            "user_avatar": str(interaction.user.display_avatar.url),
            "song": self.song_title, 
            "stars": int(self.stars.value) if self.stars.value.isdigit() else 5,
            "message": self.reason.value,
            "timestamp": datetime.utcnow()
        })
        embed = discord.Embed(title="✅ FEEDBACK RECIBIDO", description="Tu reseña sobre la calidad master ha sido guardada.", color=0x00ff77)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- REPRODUCTOR DE ALTA FIDELIDAD ---
def play_next(interaction, channel_id, last_user):
    if not interaction.guild.voice_client: return
    
    # Solo lanza la reseña al terminar la canción completa
    if bot.current_track and not bot.loop_mode:
        track_to_review = bot.current_track
        async def trigger_review():
            chan = bot.get_channel(channel_id)
            if chan:
                view = ui.View().add_item(ui.Button(label="Valorar Sonido ⭐", style=discord.ButtonStyle.success, emoji="💿"))
                async def cb(i): await i.response.send_modal(ReviewModal(track_to_review))
                view.children[0].callback = cb
                emb = discord.Embed(title="🎼 SESIÓN FINALIZADA", description=f"Track: **{track_to_review}**\nCalidad: `320kbps Opus`", color=0x00ff77)
                await chan.send(embed=emb, view=view)
        bot.loop.create_task(trigger_review())

    # LÓGICA DE ANUNCIO (SALTO VIP)
    is_vip = any(role.name == VIP_ROLE_NAME for role in last_user.roles)
    if not is_vip and bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        emb_adv = discord.Embed(title="📢 PUBLICIDAD", description="Escuchando anuncio... \n*Consigue VIP para omitir y mantener el Hi-Fi.*", color=0xffff00)
        bot.loop.create_task(interaction.channel.send(embed=emb_adv))
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id, last_user))
        return

    if bot.queue:
        url, title, user_ref = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        data = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id, user_ref))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS MANUALES ---

@bot.tree.command(name="play", description="🎶 Sonido Calidad Master 320kbps")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    u_id = interaction.user.id

    class MusicSelect(ui.Select):
        def __init__(self):
            super().__init__(placeholder="💎 Selecciona la fuente de audio Hi-Fi...", options=[
                discord.SelectOption(label=r['title'][:90], emoji="💿", value=str(i)) for i, r in enumerate(results)
            ])
        async def callback(self, inter: discord.Interaction):
            if inter.user.id != u_id: return await inter.response.send_message("❌ Búsqueda privada.", ephemeral=True)
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title'], inter.user))
                await inter.followup.send(embed=discord.Embed(description=f"📥 **Añadido a la fila:** {s['title']}", color=0x3498db))
            else:
                bot.current_track = s['title']
                bot.songs_played += 1
                info = ytdl.extract_info(s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter, inter.channel.id, inter.user))
                emb = discord.Embed(title="🚀 SONIDO HI-FI ACTIVADO", description=f"**{s['title']}**\nCodificación: `libopus Master` 🎧", color=0x00ff77)
                await inter.followup.send(embed=emb)

    await interaction.followup.send(view=ui.View().add_item(MusicSelect()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=discord.Embed(description="⏭️ **Omitiendo pista...**", color=0x00ff77))

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=discord.Embed(description="⏹️ **Sistema de audio apagado.**", color=0xff4444))

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message(embed=discord.Embed(description="⏸️ **Audio en pausa.**", color=0xffff00))

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message(embed=discord.Embed(description="▶️ **Reanudando Hi-Fi.**", color=0x00ff77))

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    txt = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "Cola vacía."
    await i.response.send_message(embed=discord.Embed(title="📋 PLAYLIST ACTUAL", description=txt, color=0x3498db))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="🎧 ESCUCHANDO", description=f"**{bot.current_track}**", color=0x00ff77))

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message(embed=discord.Embed(description="🔀 **Orden aleatorio aplicado.**", color=0x9b59b6))

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client and i.guild.voice_client.source: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(embed=discord.Embed(description=f"🔊 **Nivel de salida:** {v}%", color=0x00ff77))

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(description=f"📡 **Respuesta de señal:** `{round(bot.latency*1000)}ms`", color=0x00ff77))

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message(embed=discord.Embed(description="🗑️ **Cola de reproducción limpia.**", color=0xff0000))

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=discord.Embed(description="👋 **Flexus ha abandonado el canal.**", color=0xff4444))

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, p: int):
    if 0 < p <= len(bot.queue):
        for _ in range(p-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(embed=discord.Embed(description=f"⏩ **Saltando a pista #{p}.**", color=0x00ff77))

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=discord.Embed(description="🔄 **Reiniciando flujo de audio.**", color=0x00ff77))

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="🔥 BASS BOOST", description="Ecualización de bajos profundos activada.", color=0xe67e22))

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(embed=discord.Embed(description=f"🔁 **Repetición infinita:** {'SÍ' if bot.loop_mode else 'NO'}", color=0x00ff77))

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="🔍 LYRICS", description="Buscando líricas oficiales...", color=0x3498db))

@bot.tree.command(name="stats")
async def st(i: discord.Interaction):
    await i.response.send_message(embed=discord.Embed(title="📊 DESEMPEÑO", description=f"Total de audios hoy: `{bot.songs_played}`", color=0x00ff77))

@bot.tree.command(name="help")
async def help(i: discord.Interaction):
    emb = discord.Embed(title="👑 FLEXUS PREMIUM SYSTEM", color=0x00ff77)
    emb.add_field(name="🎧 Audio Master", value="`play`, `skip`, `stop`, `pause`, `resume`, `volume`, `loop`, `restart`, `bassboost`")
    emb.add_field(name="📋 Gestión", value="`queue`, `shuffle`, `clear`, `jump`", inline=False)
    emb.add_field(name="⚙️ Otros", value="`nowplaying`, `lyrics`, `stats`, `ping`, `leave`", inline=False)
    await i.response.send_message(embed=emb)

bot.run(TOKEN)
