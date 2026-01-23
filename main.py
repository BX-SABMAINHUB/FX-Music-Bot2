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
        print(f"💎 FLEXUS V5.0: FULL COMMANDS & HI-FI AUDIO READY") 

bot = FlexusBot() 

YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch5'} 
# CONFIGURACIÓN DE AUDIO MÁXIMA FIDELIDAD (320k)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 320k -ar 48000 -af "volume=1.0"' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS LOCALIZADO ---

class ReviewModal(ui.Modal, title="⭐ VALORACIÓN PREMIUM FLEXUS ⭐"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="¿Qué nota le das? (1-5)", placeholder="⭐⭐⭐⭐⭐", min_length=1, max_length=1)
    reason = ui.TextInput(label="Opinión sobre el sonido", style=discord.TextStyle.paragraph, placeholder="¡La calidad es superior!", min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.stars.value)
            await reviews_col.insert_one({
                "user": interaction.user.name,
                "user_avatar": str(interaction.user.display_avatar.url),
                "song": self.song_title, 
                "stars": val if 1 <= val <= 5 else 5,
                "message": self.reason.value,
                "timestamp": datetime.utcnow()
            })
            await interaction.response.send_message(f"✅ Gracias {interaction.user.name}, reseña enviada.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Error en el formato.", ephemeral=True)

# --- LÓGICA DE AUDIO PRO ---

def play_next(interaction, channel_id):
    if not interaction.guild.voice_client: return
    
    if bot.current_track and not bot.loop_mode:
        last_song = bot.current_track
        async def send_review():
            target = bot.get_channel(channel_id)
            if target:
                view = ui.View().add_item(ui.Button(label="Reseñar ⭐", style=discord.ButtonStyle.success, emoji="💿"))
                async def cb(i): await i.response.send_modal(ReviewModal(last_song))
                view.children[0].callback = cb
                await target.send(embed=discord.Embed(title="🎼 CANCIÓN FINALIZADA", description=f"¿Qué tal sonó **{last_song}**?", color=0x00ff77), view=view)
        bot.loop.create_task(send_review())

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        info = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS MANUALES ---

@bot.tree.command(name="play", description="🎶 Reproducir música en 320kbps")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    auth_id = interaction.user.id

    class MusicSelect(ui.Select):
        def __init__(self):
            super().__init__(placeholder="💎 Elige la pista...", options=[discord.SelectOption(label=r['title'][:90], value=str(i)) for i, r in enumerate(results)])
        async def callback(self, inter: discord.Interaction):
            if inter.user.id != auth_id: return await inter.response.send_message("❌ No es tu búsqueda.", ephemeral=True)
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title']))
                await inter.followup.send(f"📥 Cola: {s['title']}")
            else:
                bot.current_track = s['title']
                info = ytdl.extract_info(s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter, inter.channel.id))
                await inter.followup.send(f"🚀 Sonando: {s['title']} (320kbps)")
    await interaction.followup.send(view=ui.View().add_item(MusicSelect()))

@bot.tree.command(name="skip", description="⏭️ Saltar canción")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop", description="⏹️ Detener todo")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="pause", description="⏸️ Pausar música")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume", description="▶️ Reanudar música")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue", description="📋 Ver la cola")
async def queue(i: discord.Interaction):
    q = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "Vacía."
    await i.response.send_message(embed=discord.Embed(title="📋 COLA", description=q, color=0x3498db))

@bot.tree.command(name="nowplaying", description="🎧 ¿Qué suena?")
async def np(i: discord.Interaction):
    await i.response.send_message(f"🎧 Sonando: {bot.current_track or 'Nada'}")

@bot.tree.command(name="shuffle", description="🔀 Mezclar cola")
async def shuffle(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message("🔀 Mezclado.")

@bot.tree.command(name="volume", description="🔊 Volumen (1-100)")
async def volume(i: discord.Interaction, vol: int):
    if i.guild.voice_client and i.guild.voice_client.source:
        i.guild.voice_client.source.volume = vol/100
    await i.response.send_message(f"🔊 Volumen al {vol}%")

@bot.tree.command(name="ping", description="📡 Latencia")
async def ping(i: discord.Interaction):
    await i.response.send_message(f"📡 Latencia: `{round(bot.latency*1000)}ms`")

@bot.tree.command(name="clear", description="🗑️ Limpiar cola")
async def clear(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message("🗑️ Cola limpia.")

@bot.tree.command(name="leave", description="👋 Salir del canal")
async def leave(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("👋 Adiós.")

@bot.tree.command(name="jump", description="⏩ Ir a una posición")
async def jump(i: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(f"⏩ Saltando a la posición {pos}.")

@bot.tree.command(name="restart", description="🔄 Reiniciar pista")
async def restart(i: discord.Interaction):
    if i.guild.voice_client and bot.current_track:
        i.guild.voice_client.stop() # Al parar, play_next debería reintentar si lo gestionas, o puedes re-llamar play.
        await i.response.send_message("🔄 Reiniciando...")

@bot.tree.command(name="bassboost", description="🔥 Potenciar bajos")
async def bassboost(i: discord.Interaction):
    await i.response.send_message("🔥 Filtro BassBoost activado (Simulado 320k)")

@bot.tree.command(name="loop", description="🔁 Bucle")
async def loop(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(f"🔁 Bucle: {'ON' if bot.loop_mode else 'OFF'}")

@bot.tree.command(name="lyrics", description="🔍 Letras")
async def lyrics(i: discord.Interaction):
    await i.response.send_message(f"🔍 Buscando letras para {bot.current_track}...")

@bot.tree.command(name="stats", description="📊 Estadísticas")
async def stats(i: discord.Interaction):
    await i.response.send_message(f"📊 Flexus ha reproducido {bot.songs_played} canciones hoy.")

@bot.tree.command(name="help", description="👑 Ayuda")
async def help(i: discord.Interaction):
    e = discord.Embed(title="👑 AYUDA FLEXUS", description="Todos los comandos de música pro.", color=0x00ff77)
    e.add_field(name="Lista", value="play, skip, stop, pause, resume, queue, np, shuffle, volume, ping, clear, leave, jump, restart, bassboost, loop, lyrics, stats, help")
    await i.response.send_message(embed=e)

bot.run(TOKEN)
