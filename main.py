import discord
from discord import app_commands, ui
from discord.ext import commands
import yt_dlp
import asyncio
import os
import random
import aiohttp
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# CONFIGURACIÓN DE NÚCLEO Y BASE DE DATOS
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"
VERCEL_WEBHOOK_URL = "https://megabol.vercel.app/api/verify" # Cambia a tu URL real

# Configuración de Audio Profesional para evitar cortes
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# ==========================================
# DISEÑO DE UI (FRAMES TRABAJADOS)
# ==========================================
class FlexUI:
    @staticmethod
    def embed_frame(title, description, color=0x00ffcc, footer="FLEXUS MUSIC • MEGABOL"):
        embed = discord.Embed(
            title=f"┏━━━━━━━━━━━━━━━━━━━━┓\n┃ 🎧 {title}\n┗━━━━━━━━━━━━━━━━━━━━┛",
            description=f"\n{description}\n",
            color=color,
            timestamp=datetime.now()
        )
        embed.set_footer(text=footer)
        return embed

# ==========================================
# LÓGICA DE MÚSICA (SISTEMA DE COLA)
# ==========================================
class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.current = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        return self.queue[guild_id]

    async def play_next(self, interaction):
        guild_id = interaction.guild_id
        q = self.get_queue(guild_id)
        
        if len(q) > 0:
            track = q.pop(0)
            self.current[guild_id] = track
            
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(track['url'], download=False))
            source = data['url']
            
            interaction.guild.voice_client.play(
                discord.FFmpegPCMAudio(source, **FFMPEG_OPTIONS),
                after=lambda e: self.bot.loop.create_task(self.check_queue_after(interaction))
            )
            
            # Notificar ahora sonando
            await interaction.channel.send(embed=FlexUI.embed_frame("SONANDO AHORA", f"🎵 **{track['title']}**\n👤 Pedida por: {track['user']}"))
        else:
            # Si no hay más música, pedimos reseña (pero solo al final real)
            await interaction.channel.send(embed=FlexUI.embed_frame("FIN DE COLA", "¡Usa `/resena` para decirnos qué tal!", 0xffcc00))

    async def check_queue_after(self, interaction):
        await self.play_next(interaction)

player_manager = None # Se inicializa en el setup

# ==========================================
# CLASE PRINCIPAL DEL BOT
# ==========================================
class MegabolBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self.manager = MusicPlayer(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Comandos Sincronizados")

bot = MegabolBot()

# ==========================================
# COMANDOS DE MÚSICA (CORREGIDOS)
# ==========================================

@bot.tree.command(name="play", description="Busca y reproduce música con calidad premium")
async def play(interaction: discord.Interaction, busqueda: str):
    await interaction.response.defer()
    
    if not interaction.user.voice:
        return await interaction.followup.send(embed=FlexUI.embed_frame("ERROR", "Debes estar en un canal de voz.", 0xff0000))

    # Conexión al canal
    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    # Búsqueda
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch:{busqueda}", download=False))
    
    if 'entries' in data:
        video = data['entries'][0]
    else:
        video = data

    track = {
        'url': video['webpage_url'],
        'title': video['title'],
        'user': interaction.user.display_name
    }

    q = bot.manager.get_queue(interaction.guild_id)
    q.append(track)

    if not vc.is_playing():
        await bot.manager.play_next(interaction)
        await interaction.followup.send(embed=FlexUI.embed_frame("REPRODUCIENDO", f"Iniciando: **{track['title']}**"))
    else:
        await interaction.followup.send(embed=FlexUI.embed_frame("AÑADIDO", f"En posición **#{len(q)}**: {track['title']}"))

@bot.tree.command(name="skip", description="Salta a la siguiente canción")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        # El callback 'after' disparará la siguiente automáticamente
        await interaction.response.send_message("⏩", embed=FlexUI.embed_frame("SKIP", "Saltando a la siguiente pista...", 0x06b6d4))
    else:
        await interaction.response.send_message(embed=FlexUI.embed_frame("INFO", "No hay nada sonando.", 0x888888))

@bot.tree.command(name="mix", description="Mezcla aleatoriamente la cola actual")
async def mix(interaction: discord.Interaction):
    q = bot.manager.get_queue(interaction.guild_id)
    if len(q) < 2:
        return await interaction.response.send_message(embed=FlexUI.embed_frame("INFO", "No hay suficientes canciones para mezclar."))
    
    random.shuffle(q)
    # CORRECCIÓN DE SINTAXIS
    await interaction.response.send_message("🔀", embed=FlexUI.embed_frame("MIX", "La cola ha sido mezclada aleatoriamente.", 0x9b59b6))

@bot.tree.command(name="saltar_a", description="Salta a una posición específica de la lista")
async def saltar_a(interaction: discord.Interaction, posicion: int):
    q = bot.manager.get_queue(interaction.guild_id)
    if 0 < posicion <= len(q):
        # Eliminar las anteriores
        for _ in range(posicion - 1):
            q.pop(0)
        interaction.guild.voice_client.stop()
        # CORRECCIÓN DE SINTAXIS
        await interaction.response.send_message("⏩", embed=FlexUI.embed_frame("SALTAR A", f"Saltando directamente a la posición **#{posicion}**.", 0x00ffcc))
    else:
        await interaction.response.send_message(embed=FlexUI.embed_frame("ERROR", "Posición inválida.", 0xff0000))

# ==========================================
# COMANDOS DE CONTROL Y ESTADO
# ==========================================

@bot.tree.command(name="queue", description="Muestra la lista de reproducción")
async def queue(interaction: discord.Interaction):
    q = bot.manager.get_queue(interaction.guild_id)
    if not q:
        return await interaction.response.send_message(embed=FlexUI.embed_frame("COLA VACÍA", "No hay canciones pendientes."))
    
    lista = ""
    for i, t in enumerate(q[:10], 1):
        lista += f"**{i}.** {t['title']}\n"
    
    if len(q) > 10:
        lista += f"\n*... y {len(q) - 10} más.*"
        
    await interaction.response.send_message(embed=FlexUI.embed_frame("LISTA DE ESPERA", lista))

@bot.tree.command(name="stop", description="Detiene todo y desconecta al bot")
async def stop(interaction: discord.Interaction):
    q = bot.manager.get_queue(interaction.guild_id)
    q.clear()
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("🛑", embed=FlexUI.embed_frame("STOP", "Música detenida y cola limpiada.", 0xff0000))

# ==========================================
# SISTEMA DE RESEÑAS Y WEBHOOK
# ==========================================

class ReviewModal(ui.Modal, title="⭐ VALORACIÓN MEGABOL"):
    estrellas = ui.TextInput(label="Puntuación (1-5)", placeholder="Ej: 5", min_length=1, max_length=1)
    comentario = ui.TextInput(label="¿Qué te pareció el servicio?", style=discord.TextStyle.paragraph, min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.estrellas.value.isdigit() or not (1 <= int(self.estrellas.value) <= 5):
            return await interaction.response.send_message("Por favor, introduce un número del 1 al 5.", ephemeral=True)

        data = {
            "usuario": interaction.user.name,
            "estrellas": int(self.estrellas.value),
            "comentario": self.comentario.value,
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        # Enviar a Web de Vercel (Megabol)
        async with aiohttp.ClientSession() as session:
            try:
                await session.post(VERCEL_WEBHOOK_URL, json=data)
            except:
                pass # Si la web está 404 no crashea el bot

        await interaction.response.send_message(embed=FlexUI.embed_frame("GRACIAS", "Tu reseña ha sido enviada a MEGABOL.", 0x10b981))

@bot.tree.command(name="resena", description="Envía una reseña sobre la música")
async def resena(interaction: discord.Interaction):
    await interaction.response.send_modal(ReviewModal())

# ==========================================
# INICIO
# ==========================================
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: No se encontró el DISCORD_TOKEN en las variables de entorno.")
    else:
        bot.run(TOKEN)
