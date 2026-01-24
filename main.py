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
        print(f"💎 FLEXUS V12.5: SISTEMA FLUIDO ACTIVADO") 

bot = FlexusBot() 

# --- SISTEMA DE DISEÑO (FRAMES ÉLITE) ---
def flex_frame(title, desc, color=0x00ffcc, icon="🎧"):
    embed = discord.Embed(
        title=f"┏━━━━━━━━━━━━━━━━━┓\n┃ {icon} {title}\n┗━━━━━━━━━━━━━━━━━┛",
        description=f"**{desc}**",
        color=color
    )
    embed.set_footer(text="SISTEMA DE AUDIO V12.5 • CALIDAD 192K", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    return embed

# --- MOTOR DE AUDIO (192K SIN CARGAS) ---
YTDL_OPTS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch', 'force-ipv4': True} 
FFMPEG_OPTS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn -b:a 192k -ar 48000'}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

def play_engine(interaction, user, is_ad=False):
    if not interaction.guild.voice_client: return
    
    # Lógica de Anuncios
    is_vip = any(r.name == VIP_ROLE_NAME for r in user.roles)
    if not is_ad and not is_vip and bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTS), 
            after=lambda e: play_engine(interaction, user, is_ad=True))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        bot.songs_played += 1
        
        def after_callback(error):
            async def end_task():
                view = ui.View().add_item(ui.Button(label="VALORAR MÚSICA ⭐", style=discord.ButtonStyle.success, emoji="💿"))
                view.children[0].callback = lambda i: i.response.send_modal(ReviewModal(title))
                await interaction.channel.send(embed=flex_frame("PISTA TERMINADA", f"He reproducido: {title}"), view=view)
            bot.loop.create_task(end_task())
            
            if bot.loop_mode: bot.queue.insert(0, (url, title))
            play_engine(interaction, user)

        data = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTS), after=after_callback)

# --- MODAL RESEÑA ---
class ReviewModal(ui.Modal, title="⭐ RESEÑA PREMIUM"):
    def __init__(self, track): super().__init__(); self.track = track
    stars = ui.TextInput(label="Nota (1-5)", placeholder="⭐⭐⭐⭐⭐", max_length=1)
    msg = ui.TextInput(label="Comentario", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await reviews_col.insert_one({"usuario": interaction.user.name, "musica": self.track, "estrellas": self.stars.value, "mensaje": self.msg.value, "fecha": datetime.now()})
        await interaction.response.send_message(embed=flex_frame("EXITO", "Tu reseña se ha guardado correctamente."), ephemeral=True)

# --- LOS 19 COMANDOS MANUALES ---

@bot.tree.command(name="play", description="Busca, elige y reproduce")
async def play(i: discord.Interaction, buscar: str):
    await i.response.defer() # Esto evita el "Interacción Fallida"
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    
    class SongSelect(ui.Select):
        def __init__(self):
            opts = [discord.SelectOption(label=r['title'][:90], value=str(idx), emoji="📀") for idx, r in enumerate(results)]
            super().__init__(placeholder="💎 Elige tu canción ahora...", options=opts)

        async def callback(self, inter: discord.Interaction):
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            bot.queue.append((s['webpage_url'], s['title']))
            if not vc.is_playing(): play_engine(inter, inter.user)
            await inter.response.edit_message(embed=flex_frame("REPRODUCIENDO", f"Pista: {s['title']}"), view=None)

    await i.followup.send(embed=flex_frame("LISTA DE RESULTADOS", f"Búsqueda: {buscar}"), view=ui.View().add_item(SongSelect()))

@bot.tree.command(name="skip")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message(embed=flex_frame("SALTAR", "Cargando siguiente pista de la cola...", 0x00ffcc, "⏭️"))

@bot.tree.command(name="stop")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=flex_frame("DETENER", "Desconectado y lista borrada.", 0xff0000, "⏹️"))

@bot.tree.command(name="pause")
async def pause(i: discord.Interaction):
    if i.guild.voice_client and i.guild.voice_client.is_playing():
        i.guild.voice_client.pause()
        await i.response.send_message(embed=flex_frame("PAUSA", "La música se ha detenido.", 0xffff00, "⏸️"))

@bot.tree.command(name="resume")
async def resume(i: discord.Interaction):
    if i.guild.voice_client and i.guild.voice_client.is_paused():
        i.guild.voice_client.resume()
        await i.response.send_message(embed=flex_frame("REANUDAR", "Continuando con la pista.", 0x00ffcc, "▶️"))

@bot.tree.command(name="queue")
async def q(i: discord.Interaction):
    tracks = "\n".join([f"• {t[1]}" for t in bot.queue[:8]]) or "Cola vacía."
    await i.response.send_message(embed=flex_frame("COLA", tracks, 0x3498db, "📋"))

@bot.tree.command(name="nowplaying")
async def np(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("SONANDO", f"{bot.current_track or 'Nada'}", 0x9b59b6, "🎧"))

@bot.tree.command(name="shuffle")
async def sh(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message(embed=flex_frame("MEZCLAR", "Orden aleatorio activado.", 0x9b59b6, "🔀"))

@bot.tree.command(name="volume")
async def vol(i: discord.Interaction, nivel: int):
    if i.guild.voice_client:
        i.guild.voice_client.source.volume = nivel / 100
        await i.response.send_message(embed=flex_frame("VOLUMEN", f"Ajustado al {nivel}%", 0x00ffcc, "🔊"))

@bot.tree.command(name="ping")
async def ping(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("SISTEMA", f"Ping: {round(bot.latency*1000)}ms", 0x00ffcc, "📡"))

@bot.tree.command(name="clear")
async def cl(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message(embed=flex_frame("LIMPIAR", "Cola vaciada.", 0xff0000, "🗑️"))

@bot.tree.command(name="leave")
async def lv(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message(embed=flex_frame("DESCONECTAR", "Adiós.", 0xff0000, "👋"))

@bot.tree.command(name="jump")
async def jp(i: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos - 1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(embed=flex_frame("SALTAR A", f"Posición {pos}"), 0x00ffcc, "⏩")

@bot.tree.command(name="restart")
async def rs(i: discord.Interaction):
    if i.guild.voice_client and bot.current_track:
        i.guild.voice_client.stop()
        await i.response.send_message(embed=flex_frame("REINICIAR", "Repitiendo pista actual."), 0x00ffcc, "🔄")

@bot.tree.command(name="bassboost")
async def bb(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("BASS BOOST", "Potenciando frecuencias bajas.", 0xe67e22, "🔥"))

@bot.tree.command(name="loop")
async def lp(i: discord.Interaction):
    bot.loop_mode = not bot.loop_mode
    await i.response.send_message(embed=flex_frame("BUCLE", f"{'ACTIVADO' if bot.loop_mode else 'DESACTIVADO'}"), 0x00ffcc, "🔁")

@bot.tree.command(name="lyrics")
async def lyr(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("LYRICS", "Buscando letra..."), 0x3498db, "🔍")

@bot.tree.command(name="stats")
async def st(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("ESTADÍSTICAS", f"Canciones hoy: {bot.songs_played}"), 0x00ffcc, "📊")

@bot.tree.command(name="help")
async def h(i: discord.Interaction):
    await i.response.send_message(embed=flex_frame("AYUDA", "Usa los comandos de Slash para controlar el bot."), 0x00ffcc, "👑")

@bot.tree.command(name="admin_ban")
async def ab(i: discord.Interaction, user_id: str):
    if i.user.id == 1313950667773055010:
        await i.response.send_message(embed=flex_frame("ADMIN", f"Usuario {user_id} baneado."), ephemeral=True)

bot.run(TOKEN)
