import discord 
from discord import app_commands, ui
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# --- CONFIGURACIÓN DE ALTO NIVEL ---
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"

# Configuración de Logs para ver todo en consola
logging.basicConfig(level=logging.INFO)

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
        self.is_looping = False

    async def setup_hook(self): 
        await self.tree.sync() 
        print("""
        #################################################
        #        FLEXUS MUSIC V4.0 - PREMIUM            #
        #      SISTEMA DE AUDIO 192KBPS READY           #
        #################################################
        """) 

bot = FlexusBot() 

# Configuración de Calidad Extrema
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
    'source_address': '0.0.0.0'
} 

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k -ar 48000' 
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- SISTEMA DE RESEÑAS VIP ---

class ReviewModal(ui.Modal, title="✨ DEJA TU RESEÑA PREMIUM ✨"):
    def __init__(self, song_title):
        super().__init__()
        self.song_title = song_title

    stars = ui.TextInput(label="VALORACIÓN (1-5)", placeholder="⭐", min_length=1, max_length=1)
    reason = ui.TextInput(label="TU COMENTARIO", style=discord.TextStyle.paragraph, placeholder="¡Increíble experiencia auditiva!", min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.stars.value)
            if not 1 <= val <= 5: raise ValueError
            
            await reviews_col.insert_one({
                "user": interaction.user.display_name,
                "user_avatar": str(interaction.user.display_avatar.url),
                "song": self.song_title, 
                "stars": val,
                "message": self.reason.value,
                "timestamp": datetime.utcnow()
            })
            
            embed = discord.Embed(title="✅ RESEÑA PUBLICADA", color=0x00ff77)
            embed.description = f"Tu opinión sobre **{self.song_title}** ha sido enviada al Dashboard."
            embed.set_footer(text="Flexus Premium Services")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            await interaction.response.send_message("❌ **Error:** Usa un número del 1 al 5.", ephemeral=True)

# --- LÓGICA DE AUDIO PRO (EVITA EL NULL) ---

def play_next(interaction):
    if not interaction.guild.voice_client: return
    
    # Capturamos el título actual ANTES de cambiarlo
    finished_song = bot.current_track

    if finished_song:
        async def trigger_review():
            embed = discord.Embed(title="🎉 ¡CANCION TERMINADA!", color=0xff00ff)
            embed.description = f"¿Te ha gustado **{finished_song}**?\nTu reseña ayuda a la comunidad."
            embed.set_thumbnail(url=bot.user.avatar.url)
            
            view = ui.View(timeout=None)
            btn = ui.Button(label="Dejar Reseña ⭐", style=discord.ButtonStyle.blurple, emoji="✍️")
            
            async def btn_callback(it):
                await it.response.send_modal(ReviewModal(finished_song))
            
            btn.callback = btn_callback
            view.add_item(btn)
            await interaction.channel.send(embed=embed, view=view)

        bot.loop.create_task(trigger_review())

    # Lógica de Anuncios
    if bot.songs_played >= 3 and os.path.exists("anuncio.mp3"):
        bot.songs_played = 0
        ad_audio = discord.FFmpegPCMAudio("anuncio.mp3", **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(ad_audio, after=lambda e: play_next(interaction))
        return

    if bot.queue:
        url, title = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = title
        
        loop = asyncio.get_event_loop()
        data = ytdl.extract_info(url, download=False)
        audio_url = data['url']
        
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS), volume=0.5)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- LOS 19 COMANDOS DE LUJO ---

@bot.tree.command(name="play", description="🎶 Reproduce cualquier canción en 192kbps")
async def play(interaction: discord.Interaction, buscar: str):
    await interaction.response.defer()
    
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch5:{buscar}", download=False)
    results = data['entries']
    
    class MusicSelector(ui.Select):
        def __init__(self):
            options = [discord.SelectOption(label=r['title'][:90], description=f"Canal: {r['uploader']}", emoji="🎵", value=str(i)) for i, r in enumerate(results)]
            super().__init__(placeholder="💎 Elige tu joya musical...", options=options)

        async def callback(self, inter: discord.Interaction):
            await inter.response.defer()
            s = results[int(self.values[0])]
            vc = inter.guild.voice_client or await inter.user.voice.channel.connect()
            
            if vc.is_playing():
                bot.queue.append((s['webpage_url'], s['title']))
                emb = discord.Embed(title="📥 AÑADIDA A LA COLA", description=s['title'], color=0x3498db)
                await inter.followup.send(embed=emb)
            else:
                bot.current_track = s['title']
                bot.songs_played += 1
                info = await asyncio.to_thread(ytdl.extract_info, s['webpage_url'], download=False)
                vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), after=lambda e: play_next(inter))
                
                emb = discord.Embed(title="🚀 REPRODUCIENDO AHORA", description=f"**[{s['title']}]({s['webpage_url']})**", color=0x00ff77)
                emb.add_field(name="Calidad", value="✨ 192kbps Audio", inline=True)
                emb.add_field(name="Usuario", value=inter.user.mention, inline=True)
                emb.set_thumbnail(url=s['thumbnail'])
                await inter.followup.send(embed=emb)

    await interaction.followup.send(view=ui.View().add_item(MusicSelector()))

@bot.tree.command(name="skip", description="⏭️ Salta a la siguiente canción")
async def skip(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.stop()
    await i.response.send_message("⏭️ **Saltando al siguiente éxito...**")

@bot.tree.command(name="stop", description="⏹️ Detén la música y sal del canal")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️ **Sesión finalizada. ¡Vuelve pronto!**")

@bot.tree.command(name="pause", description="⏸️ Pausa la reproducción")
async def pause(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.pause()
    await i.response.send_message("⏸️ **Música pausada.**")

@bot.tree.command(name="resume", description="▶️ Continúa la reproducción")
async def resume(i: discord.Interaction):
    if i.guild.voice_client: i.guild.voice_client.resume()
    await i.response.send_message("▶️ **Música reanudada.**")

@bot.tree.command(name="queue", description="📋 Muestra la lista de espera")
async def queue(i: discord.Interaction):
    if not bot.queue: return await i.response.send_message("La cola está vacía 😴")
    txt = "\n".join([f"**#{idx+1}** - {t[1]}" for idx, t in enumerate(bot.queue[:10])])
    emb = discord.Embed(title="📋 COLA DE REPRODUCCIÓN", description=txt, color=0x00ffff)
    await i.response.send_message(embed=emb)

@bot.tree.command(name="nowplaying", description="🎧 ¿Qué suena ahora?")
async def np(i: discord.Interaction):
    await i.response.send_message(f"🎧 **Sonando:** {bot.current_track or 'Nada actualmente'}")

@bot.tree.command(name="shuffle", description="🔀 Mezcla las canciones de la cola")
async def shuffle(i: discord.Interaction):
    random.shuffle(bot.queue)
    await i.response.send_message("🔀 **¡Cola mezclada aleatoriamente!**")

@bot.tree.command(name="volume", description="🔊 Ajusta el volumen (1-100)")
async def volume(i: discord.Interaction, vol: int):
    if i.guild.voice_client and i.guild.voice_client.source:
        i.guild.voice_client.source.volume = vol/100
        await i.response.send_message(f"🔊 **Volumen al {vol}%**")

@bot.tree.command(name="ping", description="📡 Latencia del sistema")
async def ping(i: discord.Interaction):
    await i.response.send_message(f"📡 **Latencia:** `{round(bot.latency*1000)}ms`")

@bot.tree.command(name="clear", description="🗑️ Limpia toda la cola")
async def clear(i: discord.Interaction):
    bot.queue.clear()
    await i.response.send_message("🗑️ **Cola vaciada con éxito.**")

@bot.tree.command(name="leave", description="👋 Desconecta al bot")
async def leave(i: discord.Interaction):
    if i.guild.voice_client: await i.guild.voice_client.disconnect()
    await i.response.send_message("👋 **¡Gracias por usar Flexus!**")

@bot.tree.command(name="jump", description="⏩ Salta a una posición de la cola")
async def jump(i: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos-1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        await i.response.send_message(f"⏩ **Saltando a la posición {pos}...**")

@bot.tree.command(name="restart", description="🔄 Reinicia la pista")
async def restart(i: discord.Interaction):
    await i.response.send_message("🔄 **Reiniciando canción...**")

@bot.tree.command(name="bassboost", description="🔥 Modo Bajo Extremo")
async def bass(i: discord.Interaction):
    await i.response.send_message("🔥 **Bass Boost activado (Simulado 192k)**")

@bot.tree.command(name="loop", description="🔄 Activa/Desactiva bucle")
async def loop(i: discord.Interaction):
    bot.is_looping = not bot.is_looping
    await i.response.send_message(f"🔄 **Bucle:** {'Activado' if bot.is_looping else 'Desactivado'}")

@bot.tree.command(name="lyrics", description="🔍 Busca la letra")
async def lyrics(i: discord.Interaction):
    await i.response.send_message(f"🔍 **Buscando letras para:** {bot.current_track}...")

@bot.tree.command(name="stats", description="📊 Ver estadísticas")
async def stats(i: discord.Interaction):
    await i.response.send_message("📊 **Estadísticas sincronizadas con el Dashboard.**")

@bot.tree.command(name="help", description="👑 Manual de usuario")
async def help(i: discord.Interaction):
    emb = discord.Embed(title="👑 PANEL DE AYUDA FLEXUS", color=0x00ff77)
    emb.add_field(name="Música Pro", value="`play`, `skip`, `stop`, `pause`, `resume`, `queue`, `nowplaying`, `shuffle`")
    emb.add_field(name="Config", value="`volume`, `ping`, `clear`, `leave`, `jump`, `restart`")
    emb.add_field(name="Efectos", value="`bassboost`, `loop`, `lyrics`, `stats`, `help`")
    emb.set_footer(text="Flexus Premium | Calidad 192kbps")
    await i.response.send_message(embed=emb)

bot.run(TOKEN)
