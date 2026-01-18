import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os

# 1. DEFINICIÓN DEL BOT (Esto es lo que falta en IMG_0138)
TOKEN = os.getenv("DISCORD_TOKEN")

class FlexusBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="fx!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ FLEXUS conectado como {self.user}")

bot = FlexusBot()

# 2. CONFIGURACIÓN DE AUDIO
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# 3. COMANDOS
@bot.tree.command(name="play", description="Reproduce música")
async def play(interaction: discord.Interaction, busqueda: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ ¡Entra a un canal de voz!", ephemeral=True)

    await interaction.response.defer()
    
    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(busqueda, download=False))
        if 'entries' in data:
            data = data['entries'][0]
        
        url = data['url']
        titulo = data['title']

        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()

        if vc.is_playing():
            vc.stop()
            
        vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))
        await interaction.followup.send(f"🎶 Reproduciendo: **{titulo}**")

    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send(f"❌ Error al reproducir. Revisa los logs.")

@bot.tree.command(name="stop", description="Detiene el bot")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Desconectado.")

# 4. EJECUCIÓN
bot.run(TOKEN)
