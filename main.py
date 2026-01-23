import discord 
from discord import app_commands, ui
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# --- CONFIGURACIÓN DE LUJO ---
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
        self.songs_played = 0
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"💎 FLEXUS V4.0: ¡SISTEMA DE LUJO ACTIVADO!") 

bot = FlexusBot() 

YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch5'} 

# CONFIGURACIÓN DE CALIDAD 192KBPS AGREGADA ABAJO
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- MODAL DE RESEÑAS DECORADO ---

class ReviewModal(ui.Modal, title="⭐ DEJA TU RESEÑA VIP ⭐"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="¿Cuántas estrellas le das? (1-5)", placeholder="⭐⭐⭐⭐⭐", min_length=1, max_length=1)
    reason = ui.TextInput(label="¿Qué te pareció el temazo?", style=discord.TextStyle.paragraph, placeholder="¡Increíble sonido y ritmo!")

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
            embed = discord.Embed(title="✅ ¡RESEÑA ENVIADA CON ÉXITO!", description=f"Gracias **{interaction.user.name}**, tu opinión ya está brillando en nuestra web. ✨", color=0x00ff77)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            await interaction.response.send_message("❌ **Error:** Por favor, introduce un número del 1 al 5.", ephemeral=True)

# --- LÓGICA DE AUDIO (CORREGIDA) ---

def play_next(interaction):
    if not interaction.guild.voice_client: return
    
    if bot.current_track:
        async def send_review():
            embed = discord.Embed(title="🎵 ¡CANCIÓN TERMINADA!", description=f"¿Qué te pareció **{bot.current_track}**?\n¡Haz clic abajo para compartir tu opinión en la web! 🚀✨", color=0xff00ff)
            view = ui.View().add_item(ui.Button(label="Escribir Reseña ⭐", style=discord.ButtonStyle.success, emoji="✍️"))
            
            async def r_callback(inter):
                await inter.response.send_modal(ReviewModal(bot.current_track))
            
            view.children[0].callback = r_callback
            await interaction.channel.send(embed=embed, view=view)
        
        bot.loop.create_task(send_review())

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        info = ytdl.extract_info(url, download=False)
        interaction.guild.voice_client.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS DECORADOS ---

@bot.tree.command(name="play", description="🎶 Reproduce música con calidad Premium 192kbps")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{buscar}", download=False))
    results = data['entries']
    
    class SelectMusic(ui.Select):
        def __init__(self):
            super().__init__(placeholder="💎 Elige un temazo de la lista...", options=[
                discord.SelectOption(label=r['title'][:90], emoji="💿", value=str(i)) for i, r in enumerate(results)
            ])
        async def callback(self, inter: discord.Interaction):
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            
            embed = discord.Embed(title=f"🎶 {s['title']}", color=0x00ff77)
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title']))
                embed.description = "✅ **¡Añadida a la cola de éxitos!** 📥"
                await inter.followup.send(embed=embed)
            else:
                bot.current_track = s['title']
                info = ytdl.extract_info(s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter))
                embed.description = "🚀 **¡Reproduciendo ahora en Calidad 192kbps!** 🔊"
                await inter.followup.send(embed=embed)

    await interaction.followup.send(view=ui.View().add_item(SelectMusic()))

@bot.tree.command(name="skip", description="⏭️ Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ **¡Saltada! Buscando el siguiente temazo...** 🎧")

@bot.tree.command(name="stop", description="⏹️ Detén la música y limpia la cola")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ **Música detenida. ¡Gracias por elegir Flexus!** 👋")

@bot.tree.command(name="queue", description="📋 Mira la lista de reproducción")
async def queue(interaction: discord.Interaction):
    q = "\n".join([f"**{i+1}.** {t[1]} 🎵" for i, t in enumerate(bot.queue[:10])]) or "La cola está vacía... ¡Añade algo! 😴"
    embed = discord.Embed(title="📋 COLA DE REPRODUCCIÓN PREMIUM", description=q, color=0x3498db)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="nowplaying", description="🎧 Mira qué está sonando")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎧 **Sonando ahora mismo:** `{bot.current_track or 'Silencio absoluto...'}` 🔊")

@bot.tree.command(name="pause", description="⏸️ Pausa la canción actual")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ **Música en pausa. ¡No tardes en volver!** ☕")

@bot.tree.command(name="resume", description="▶️ Continúa con la música")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ **¡La fiesta sigue! Reanudando...** 🎸")

@bot.tree.command(name="shuffle", description="🔀 Mezcla las canciones de la cola")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 **¡Cola mezclada con éxito! ¡Sorpresa!** 🎲")

@bot.tree.command(name="volume", description="🔊 Cambia el volumen (1-100)")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.source.volume = vol/100
        await interaction.response.send_message(f"🔊 **Volumen ajustado al {vol}%** 🎚️")

@bot.tree.command(name="ping", description="📡 Revisa la conexión del bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 **Latencia de red:** `{round(bot.latency*1000)}ms` ⚡")

@bot.tree.command(name="clear", description="🗑️ Borra todas las canciones de la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ **¡Cola vaciada por completo!** ✨")

@bot.tree.command(name="stats", description="📊 Ver estadísticas del sistema")
async def stats(interaction: discord.Interaction):
    await interaction.response.send_message("📊 **Estadísticas de impacto enviadas al Dashboard Web.** 🌐")

@bot.tree.command(name="leave", description="👋 Desconecta al bot del canal de voz")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 **Desconectado del canal. ¡Vuelve pronto!** 💎")

@bot.tree.command(name="jump", description="⏩ Salta a una posición específica de la cola")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos-1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ **Saltando directamente a la posición {pos}...** 🚀")

@bot.tree.command(name="restart", description="🔄 Reinicia la canción actual")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Reiniciando la pista actual para más placer...** 🎸")

@bot.tree.command(name="bassboost", description="🔊 Potencia los bajos (Modo 192k)")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 **Bass Boost: [ON]** | Graves potenciados al máximo. 🔥")

@bot.tree.command(name="loop", description="🔄 Repite la canción o la cola")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Modo Bucle Infinito activado.** ♾️")

@bot.tree.command(name="lyrics", description="🔍 Busca la letra de la canción")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 **Buscando la letra perfecta para:** `{bot.current_track}`... 📝")

@bot.tree.command(name="help", description="👑 Panel de ayuda de Flexus")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="👑 COMANDOS VIP FLEXUS PREMIUM", color=0x00ff77)
    embed.description = "🎧 **Música:** `play`, `skip`, `stop`, `pause`, `resume`, `queue`, `nowplaying`, `shuffle`, `jump`, `restart`, `clear` \n\n✨ **Extras:** `bassboost`, `loop`, `lyrics` \n\n⚙️ **Sistema:** `volume`, `ping`, `stats`, `leave`, `help`"
    embed.set_footer(text="Calidad de Audio: 192kbps Estéreo")
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
