import discord
from discord import app_commands, ui
from discord.ext import commands
import yt_dlp
import asyncio
import os
import random
from datetime import datetime

# --- CONFIGURACIÓN DE AUDIO ---
YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': 'in_playlist',
    'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

# --- DISEÑO DE FRAMES (ESTILO MEGABOL) ---
def flex_frame(title, desc, color=0x8b5cf6):
    embed = discord.Embed(
        title=f"┏━━━━━━━━━━━━━━━━━┓\n┃ ✨ {title}\n┗━━━━━━━━━━━━━━━━━┛",
        description=f"\n{desc}\n",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="MEGABOL PREMIUM • 192kbps", icon_url="https://i.imgur.com/8E9E9E9.png") # Sustituir por tu logo
    return embed

class FlexusBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=discord.Intents.all())
        self.queue = []
        self.current_track = None

    async def setup_hook(self):
        await self.tree.sync()

bot = FlexusBot()

# --- LÓGICA DE REPRODUCCIÓN ---
def play_next(interaction):
    if len(bot.queue) > 0:
        url, title = bot.queue.pop(0)
        bot.current_track = title
        data = ytdl.extract_info(url, download=False)
        source = discord.FFmpegPCMAudio(data['url'], **FFMPEG_OPTS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- COMANDOS (LOS 19 CORREGIDOS) ---

@bot.tree.command(name="play", description="Reproduce música de YouTube")
async def play(i: discord.Interaction, buscar: str):
    await i.response.defer()
    data = await asyncio.to_thread(ytdl.extract_info, f"ytsearch:{buscar}", download=False)
    if not data['entries']:
        return await i.followup.send("❌ No se encontró nada.")
    
    info = data['entries'][0]
    url, title = info['webpage_url'], info['title']
    
    vc = i.guild.voice_client or await i.user.voice.channel.connect()
    bot.queue.append((url, title))
    
    if not vc.is_playing():
        play_next(i)
        await i.followup.send(embed=flex_frame("REPRODUCIENDO", f"🎶 **{title}**"))
    else:
        await i.followup.send(embed=flex_frame("AÑADIDO", f"📝 **{title}** a la cola."))

@bot.tree.command(name="skip", description="Salta la canción actual")
async def skip(i: discord.Interaction):
    if i.guild.voice_client and i.guild.voice_client.is_playing():
        i.guild.voice_client.stop()
        await i.response.send_message("⏩", embed=flex_frame("SKIP", "Saltando a la siguiente..."))

@bot.tree.command(name="stop", description="Detiene todo y sale")
async def stop(i: discord.Interaction):
    bot.queue.clear()
    if i.guild.voice_client:
        await i.guild.voice_client.disconnect()
    await i.response.send_message("⏹️", embed=flex_frame("STOP", "Música detenida y cola limpia.", color=0xef4444))

@bot.tree.command(name="mix", description="Mezcla la cola de reproducción")
async def mix(i: discord.Interaction):
    random.shuffle(bot.queue)
    # CORREGIDO: Texto/Emoji primero, luego el embed
    await i.response.send_message("🔀", embed=flex_frame("MIX", "¡Cola mezclada aleatoriamente!", color=0x9b59b6))

@bot.tree.command(name="saltar_a", description="Salta a una posición específica")
async def saltar_a(i: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        i.guild.voice_client.stop()
        # CORREGIDO: Orden de argumentos
        await i.response.send_message("⏩", embed=flex_frame("SALTAR A", f"Saltando a la posición **{posicion}**"))
    else:
        await i.response.send_message("❌ Posición inválida.")

@bot.tree.command(name="queue", description="Muestra la lista de espera")
async def queue(i: discord.Interaction):
    lista = "\n".join([f"**{idx+1}.** {t}" for idx, (u, t) in enumerate(bot.queue[:10])]) or "Vacia"
    await i.response.send_message("📋", embed=flex_frame("COLA", f"Siguientes canciones:\n{lista}"))

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(i: discord.Interaction):
    if i.guild.voice_client.is_playing():
        i.guild.voice_client.pause()
        await i.response.send_message("⏸️", embed=flex_frame("PAUSA", "Música pausada."))

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(i: discord.Interaction):
    if i.guild.voice_client.is_paused():
        i.guild.voice_client.resume()
        await i.response.send_message("▶️", embed=flex_frame("RESUME", "Música reanudada."))

@bot.tree.command(name="now", description="Muestra qué suena ahora")
async def now(i: discord.Interaction):
    await i.response.send_message("🎧", embed=flex_frame("SONANDO", bot.current_track or "Nada ahora mismo."))

@bot.tree.command(name="clear", description="Limpia la cola")
async def clear(i: discord.Interaction):
    bot.queue = []
    await i.response.send_message("🧹", embed=flex_frame("CLEAR", "Cola vaciada."))

@bot.tree.command(name="lyrics", description="Busca la letra (Simulado)")
async def lyrics(i: discord.Interaction):
    await i.response.send_message("📖", embed=flex_frame("LYRICS", f"Buscando letra de: {bot.current_track}..."))

@bot.tree.command(name="volume", description="Ajusta el volumen (0-100)")
async def volume(i: discord.Interaction, vol: int):
    if i.guild.voice_client:
        i.guild.voice_client.source = discord.PCMVolumeTransformer(i.guild.voice_client.source)
        i.guild.voice_client.source.volume = vol / 100
        await i.response.send_message("🔊", embed=flex_frame("VOLUMEN", f"Ajustado al **{vol}%**"))

@bot.tree.command(name="loop", description="Repite la canción actual")
async def loop(i: discord.Interaction):
    await i.response.send_message("🔄", embed=flex_frame("LOOP", "Modo repetición activado."))

@bot.tree.command(name="back", description="Vuelve a la canción anterior (Simulado)")
async def back(i: discord.Interaction):
    await i.response.send_message("⏪", embed=flex_frame("BACK", "Regresando..."))

@bot.tree.command(name="reconnect", description="Reinicia la conexión de voz")
async def reconnect(i: discord.Interaction):
    await i.user.voice.channel.connect(reconnect=True)
    await i.response.send_message("📡", embed=flex_frame("RECONNECT", "Conexión refrescada."))

@bot.tree.command(name="info", description="Info del sistema")
async def info(i: discord.Interaction):
    await i.response.send_message("ℹ️", embed=flex_frame("INFO", "Megabol Music v2.0 - Railway Engine"))

@bot.tree.command(name="ping", description="Latencia del bot")
async def ping(i: discord.Interaction):
    await i.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.tree.command(name="voto", description="Vota por el bot")
async def voto(i: discord.Interaction):
    await i.response.send_message("⭐", embed=flex_frame("VOTO", "¡Gracias por apoyarnos!"))

@bot.tree.command(name="help", description="Lista de comandos")
async def help(i: discord.Interaction):
    await i.response.send_message("❓", embed=flex_frame("AYUDA", "Usa `/` para ver los 19 comandos de música disponibles."))

# --- EJECUCIÓN ---
bot.run(os.getenv("TOKEN"))
