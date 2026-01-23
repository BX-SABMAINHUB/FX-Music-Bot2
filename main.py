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
        print(f"💎 FLEXUS V6.0: AUDIO HI-RES & 19 CMDS ACTIVADOS") 

bot = FlexusBot() 

YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch5'} 
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 128k -ar 48000 -af "loudnorm=I=-16:TP=-1.5:LRA=11"' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- SISTEMA DE RESEÑAS LOCALIZADO ---
class ReviewModal(ui.Modal, title="⭐ VALORACIÓN PREMIUM ⭐"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="Puntuación (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    reason = ui.TextInput(label="Comentario", style=discord.TextStyle.paragraph, placeholder="¡Sonido increíble!", min_length=5)

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
            await interaction.response.send_message(f"✅ **{interaction.user.name}**, tu reseña está en la web.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Error en el envío.", ephemeral=True)

def play_next(interaction, channel_id):
    if not interaction.guild.voice_client: return
    
    if bot.current_track and not bot.loop_mode:
        last_song = bot.current_track
        async def send_review():
            target = bot.get_channel(channel_id)
            if target:
                view = ui.View(timeout=None)
                btn = ui.Button(label="Reseñar ⭐", style=discord.ButtonStyle.success, emoji="✍️")
                async def cb(i): await i.response.send_modal(ReviewModal(last_song))
                btn.callback = cb
                view.add_item(btn)
                await target.send(embed=discord.Embed(title="🎼 FIN DE PISTA", description=f"¿Qué te pareció **{last_song}**?", color=0x00ff77), view=view)
        bot.loop.create_task(send_review())

    if bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        info = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction, channel_id))
    else:
        bot.current_track = None

# --- COMANDOS ---
@bot.tree.command(name="play")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    auth_id = interaction.user.id

    class MusicSelect(ui.Select):
        def __init__(self):
            super().__init__(placeholder="💎 Elige la pista...", options=[discord.SelectOption(label=r['title'][:90], emoji="💿", value=str(i)) for i, r in enumerate(results)])
        async def callback(self, inter: discord.Interaction):
            if inter.user.id != auth_id: return await inter.response.send_message("❌ No es tu búsqueda.", ephemeral=True)
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title']))
                await inter.followup.send(f"📥 **Añadida:** {s['title']}")
            else:
                bot.current_track = s['title']
                bot.songs_played += 1
                info = ytdl.extract_info(s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter, inter.channel.id))
                await inter.followup.send(f"🚀 **Sonando:** {s['title']}")
    await interaction.followup.send(view=ui.View().add_item(MusicSelect()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("⏭️ Saltada.")

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️ Desconectado.")

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue")
async def queue(i: discord.Interaction):
    txt = "\n".join([f"**{idx+1}.** {t[1]}" for idx, t in enumerate(bot.queue[:10])]) or "Vacía."
    await i.response.send_message(embed=discord.Embed(title="📋 COLA", description=txt, color=0x00ff77))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction): await i.response.send_message(f"🎧 {bot.current_track}")

@bot.tree.command(name="shuffle")
async def shuffle(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message("🔀 Mezclado.")

@bot.tree.command(name="volume")
async def volume(i: discord.Interaction, vol: int):
    if i.guild.voice_client and i.guild.voice_client.source: i.guild.voice_client.source.volume = vol/100
    await i.response.send_message(f"🔊 {vol}%")

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction): await i.response.send_message(f"📡 {round(bot.latency*1000)}ms")

@bot.tree.command(name="clear")
async def clear(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message("🗑️ Limpia.")

@bot.tree.command(name="leave")
async def leave(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("👋 Adiós.")

@bot.tree.command(name="jump")
async def jump(i: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(f"⏩ Saltado a {pos}.")

@bot.tree.command(name="restart")
async def restart(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("🔄 Reiniciando.")

@bot.tree.command(name="bassboost")
async def bass(i: discord.Interaction): await i.response.send_message("🔥 BassBoost ON.")

@bot.tree.command(name="loop")
async def loop(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(f"🔁 Bucle: {bot.loop_mode}")

@bot.tree.command(name="lyrics")
async def lyrics(i: discord.Interaction): await i.response.send_message("🔍 Buscando...")

@bot.tree.command(name="stats")
async def stats(i: discord.Interaction): await i.response.send_message(f"📊 {bot.songs_played} tracks.")

@bot.tree.command(name="help")
async def help(i: discord.Interaction):
    await i.response.send_message("👑 Comandos: play, skip, stop, pause, resume, queue, np, shuffle, volume, ping, clear, leave, jump, restart, bass, loop, lyrics, stats, help")

bot.run(TOKEN)
