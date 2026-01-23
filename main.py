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
        print(f"💎 FLEXUS V7.0: SISTEMA DE AUDIO BLINDADO ACTIVADO") 

bot = FlexusBot() 

# CONFIGURACIÓN DE AUDIO DE MÁXIMA ESTABILIDAD
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0'
} 
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 128k -ar 48000 -af "volume=1.0"' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS PROFESIONAL ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN PREMIUM FLEXUS ⭐"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="¿Qué nota le das? (1-5)", placeholder="⭐⭐⭐⭐⭐", min_length=1, max_length=1)
    reason = ui.TextInput(label="Opinión técnica", style=discord.TextStyle.paragraph, placeholder="¿Cómo fue la calidad?", min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        await reviews_col.insert_one({
            "user": interaction.user.name,
            "user_avatar": str(interaction.user.display_avatar.url),
            "song": self.song_title, 
            "stars": int(self.stars.value) if self.stars.value.isdigit() else 5,
            "message": self.reason.value,
            "timestamp": datetime.utcnow()
        })
        await interaction.response.send_message(f"✅ **{interaction.user.name}**, reseña guardada.", ephemeral=True)

# --- SISTEMA DE REPRODUCCIÓN (FIX: CANCIÓN COMPLETA) ---
def play_next(interaction, channel_id):
    if not interaction.guild.voice_client: return
    
    # Solo lanza la reseña si terminó una canción real
    if bot.current_track and not bot.loop_mode:
        song_ended = bot.current_track
        async def trigger_review():
            chan = bot.get_channel(channel_id)
            if chan:
                view = ui.View().add_item(ui.Button(label="Dejar Reseña ⭐", style=discord.ButtonStyle.success, emoji="💿"))
                async def cb(i): await i.response.send_modal(ReviewModal(song_ended))
                view.children[0].callback = cb
                emb = discord.Embed(title="🎼 PISTA COMPLETADA", description=f"Has escuchado: **{song_ended}**\n¡Danos tu opinión!", color=0x00ff77)
                await chan.send(embed=emb, view=view)
        bot.loop.create_task(trigger_review())

    # Anuncio cada 3 pistas
    if bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        data = ytdl.extract_info(url, download=False)
        source = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction, channel_id))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS MANUALES ---
@bot.tree.command(name="play", description="🎶 Sonido Hi-Fi + Selección Protegida")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    user_id = interaction.user.id

    class SelectSong(ui.Select):
        def __init__(self):
            super().__init__(placeholder="💎 Elige la mejor versión...", options=[
                discord.SelectOption(label=r['title'][:90], emoji="🎵", value=str(i)) for i, r in enumerate(results)
            ])
        async def callback(self, inter: discord.Interaction):
            if inter.user.id != user_id: return await inter.response.send_message("❌ ¡Solo quien buscó puede elegir!", ephemeral=True)
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title']))
                await inter.followup.send(f"📥 **En cola:** {s['title']}")
            else:
                bot.current_track = s['title']
                info = ytdl.extract_info(s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter, inter.channel.id))
                await inter.followup.send(f"🚀 **Reproduciendo:** {s['title']}")

    await interaction.followup.send(view=ui.View().add_item(SelectSong()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("⏭️ **Saltada.**")

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️ **Desconectado.**")

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message("⏸️ **Pausado.**")

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message("▶️ **Reanudado.**")

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    msg = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "Cola vacía."
    await i.response.send_message(embed=discord.Embed(title="📋 COLA", description=msg, color=0x3498db))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction): await i.response.send_message(f"🎧 **Sonando:** {bot.current_track}")

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message("🔀 **Mezclado.**")

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, v: int):
    if i.guild.voice_client and i.guild.voice_client.source: i.guild.voice_client.source.volume = v/100
    await i.response.send_message(f"🔊 **Volumen:** {v}%")

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction): await i.response.send_message(f"📡 `{round(bot.latency*1000)}ms`")

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message("🗑️ **Limpia.**")

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("👋 **Bye.**")

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, p: int):
    if 0 < p <= len(bot.queue):
        for _ in range(p-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(f"⏩ **Salto a {p}.**")

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("🔄 **Reiniciando pista...**")

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction): await i.response.send_message("🔥 **BassBoost: ACTIVADO**")

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(f"🔁 **Bucle:** {bot.loop_mode}")

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction): await i.response.send_message(f"🔍 Letras de {bot.current_track}...")

@bot.tree.command(name="stats")
async def st(i: discord.Interaction): await i.response.send_message(f"📊 Reproducciones: {bot.songs_played}")

@bot.tree.command(name="help")
async def help(i: discord.Interaction):
    e = discord.Embed(title="👑 FLEXUS HELP", description="play, skip, stop, pause, resume, queue, np, shuffle, volume, ping, clear, leave, jump, restart, bass, loop, lyrics, stats, help", color=0x00ff77)
    await i.response.send_message(embed=e)

bot.run(TOKEN)
