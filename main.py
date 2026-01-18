import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os

# CONFIGURACIÓN SEGURA
TOKEN = os.getenv("DISCORD_TOKEN")

# Opciones optimizadas para evitar que el bot se quede "pensando"
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'force_generic_extractor': False,
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
        await self.tree.sync()
        print(f"✅ FLEXUS listo y comandos sincronizados")

bot = MusicBot()

async def get_audio_info(query):
    loop = asyncio.get_event_loop()
    # Usamos extract_info con download=False para obtener el enlace directo rápidamente
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
    if 'entries' in data:
        data = data['entries'][0]
    return {'url': data['url'], 'title': data['title']}

def play_next(interaction, gid):
    if gid in bot.queues and bot.queues[gid]:
        song = bot.queues[gid].pop(0)
        vc = interaction.guild.voice_client
        if vc:
            vc.play(discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS), 
                    after=lambda e: play_next(interaction, gid))

@bot.tree.command(name="play", description="Reproduce música (Usa nombre+artista o una URL)")
@app_commands.describe(busqueda="Nombre de la canción y artista", url="URL de YouTube (Opcional)")
async def play(interaction: discord.Interaction, busqueda: str = None, url: str = None):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ ¡Debes estar en un canal de voz!", ephemeral=True)
    
    if not busqueda and not url:
        return await interaction.response.send_message("❌ Debes poner un nombre o una URL.", ephemeral=True)

    await interaction.response.defer() # Esto evita que el comando expire mientras busca
    
    query = url if url else busqueda
    
    try:
        info = await get_audio_info(query)
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        gid = interaction.guild.id
        if gid not in bot.queues: self.queues[gid] = []

        if vc.is_playing():
            bot.queues[gid].append(info)
            await interaction.followup.send(f"⌛ Añadida a la cola: **{info['title']}**")
        else:
            vc.play(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), 
                    after=lambda e: play_next(interaction, gid))
            await interaction.followup.send(f"▶️ Reproduciendo ahora: **{info['title']}**")
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send(f"❌ No pude reproducir eso. Intenta con un nombre diferente.")

# Comandos básicos adicionales
@bot.tree.command(name="skip", description="Salta la canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Canción saltada.")

@bot.tree.command(name="stop", description="Detiene el bot")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        bot.queues[interaction.guild.id] = []
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏹️ Música detenida.")

bot.run(TOKEN)
