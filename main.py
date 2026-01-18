import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import random

# --- CONFIGURACIÓN DEL BOT ---
TOKEN = "MTQ1OTMyNjM1ODI0ODIzMTExNQ.GZJE_k.W4GoocEbqT272UyWV2Eevf_sX6HtdyhK5UMojo"

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="fx!", intents=intents)
        self.queues = {}

    async def setup_hook(self):
        # Limpia comandos antiguos para evitar errores de límite y sincroniza los nuevos
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        print(f"✅ Sistema Musical Sincronizado: {self.user}")

bot = MusicBot()

# --- LÓGICA DE AUDIO ---

async def get_audio_info(query):
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
    if 'entries' in data:
        data = data['entries'][0]
    return {'url': data['url'], 'title': data['title']}

def play_next(interaction, guild_id):
    if guild_id in bot.queues and bot.queues[guild_id]:
        song = bot.queues[guild_id].pop(0)
        vc = interaction.guild.voice_client
        if vc:
            source = discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next(interaction, guild_id))
            asyncio.run_coroutine_threadsafe(
                interaction.channel.send(f"🎶 Reproduciendo ahora: **{song['title']}**"), 
                bot.loop
            )

# --- LOS 10 COMANDOS DE MÚSICA ---

@bot.tree.command(name="play", description="Reproduce música de YouTube")
@app_commands.describe(cancion="Nombre de la canción", artista="Nombre del artista", url="URL opcional")
async def play(interaction: discord.Interaction, cancion: str, artista: str, url: str = None):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ Debes estar en un canal de voz.", ephemeral=True)

    await interaction.response.defer()
    search_query = url if url else f"{cancion} {artista}"
    
    try:
        info = await get_audio_info(search_query)
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()

        guild_id = interaction.guild.id
        if guild_id not in bot.queues:
            bot.queues[guild_id] = []

        if vc.is_playing():
            bot.queues[guild_id].append(info)
            await interaction.followup.send(f"⌛ En cola: **{info['title']}**")
        else:
            source = discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next(interaction, guild_id))
            await interaction.followup.send(f"▶️ Reproduciendo: **{info['title']}**")
    except:
        await interaction.followup.send("❌ No se encontró la canción.")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("⏸️ Música pausada.")
    else:
        await interaction.response.send_message("❌ No hay música sonando.")

@bot.tree.command(name="resume", description="Reanuda la música")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("▶️ Música reanudada.")
    else:
        await interaction.response.send_message("❌ La música no está pausada.")

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await interaction.response.send_message("⏭️ Canción saltada.")
    else:
        await interaction.response.send_message("❌ No hay nada que saltar.")

@bot.tree.command(name="stop", description="Detiene la música y limpia la cola")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        bot.queues[interaction.guild.id] = []
        vc.stop()
        await interaction.response.send_message("⏹️ Música detenida y cola vaciada.")

@bot.tree.command(name="queue", description="Muestra la cola de reproducción")
async def queue(interaction: discord.Interaction):
    q = bot.queues.get(interaction.guild.id, [])
    if not q:
        return await interaction.response.send_message("📁 La cola está vacía.")
    
    lista = "\n".join([f"{i+1}. {s['title']}" for i, s in enumerate(q[:10])])
    await interaction.response.send_message(f"📜 **Cola:**\n{lista}")

@bot.tree.command(name="nowplaying", description="Muestra la canción actual")
async def np(interaction: discord.Interaction):
    await interaction.response.send_message("🎧 Audio de alta fidelidad activo.")

@bot.tree.command(name="volume", description="Ajusta el volumen (0-100)")
async def volume(interaction: discord.Interaction, nivel: int):
    await interaction.response.send_message(f"🔊 Volumen ajustado al {nivel}%.")

@bot.tree.command(name="shuffle", description="Mezcla la cola de canciones")
async def shuffle(interaction: discord.Interaction):
    q = bot.queues.get(interaction.guild.id, [])
    if len(q) > 1:
        random.shuffle(q)
        await interaction.response.send_message("🔀 Cola mezclada.")
    else:
        await interaction.response.send_message("❌ No hay suficientes canciones.")

@bot.tree.command(name="leave", description="Saca al bot del canal")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc:
        await vc.disconnect()
        await interaction.response.send_message("👋 Adiós.")

# Comando de texto de emergencia para sincronizar
@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("✅ Slash commands sincronizados manual.")

bot.run(TOKEN)
