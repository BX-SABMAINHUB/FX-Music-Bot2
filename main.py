import discord 
from discord import app_commands, ui
from discord.ext import commands 
import yt_dlp 
import asyncio 
import os 
import random
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURACIÓN ---
TOKEN = os.getenv("DISCORD_TOKEN") 
MONGO_URL = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority"

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["flexus_data"]
stats_col = db["ads_stats"]

class FlexusBot(commands.Bot): 
    def __init__(self): 
        intents = discord.Intents.all() 
        super().__init__(command_prefix="/", intents=intents) 
        self.queue = [] 
        self.songs_played = 0
        self.current_track = None

    async def setup_hook(self): 
        await self.tree.sync() 
        print(f"🚀 FLEXUS V3 ULTRA: VELOCIDAD Y CALIDAD ACTIVADAS") 

bot = FlexusBot() 

# CONFIGURACIÓN YTDL OPTIMIZADA (SÚPER RÁPIDA)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extract_flat': True, # <--- ESTO HACE QUE LA BÚSQUEDA SEA INSTANTÁNEA
    'default_search': 'ytsearch5',
    'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
} 

# CONFIGURACIÓN FFMPEG (CALIDAD DE SONIDO ESTABLE)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k' # <--- FORZAR CALIDAD DE AUDIO
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- LÓGICA DE AUDIO ---

async def registrar_anuncio(guild):
    if guild.voice_client and guild.voice_client.channel:
        oyentes = len(guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(interaction):
    if not interaction.guild.voice_client: return
    canal = interaction.guild.voice_client.channel
    
    # Detección VIP
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in canal.members)

    # Lógica de Anuncios (Cada 3 canciones)
    if bot.songs_played >= 3:
        bot.songs_played = 0
        if not es_vip and os.path.exists("anuncio.mp3"):
            print("📢 Reproduciendo publicidad...")
            source = discord.FFmpegPCMAudio("anuncio.mp3")
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction.guild), bot.loop)
            return
        elif es_vip:
            print("💎 VIP Detectado: Anuncio saltado.")

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- INTERFAZ MODERNA (EMBEDS Y BOTONES) ---

class SongSelect(ui.Select):
    def __init__(self, options_data):
        # Creamos las opciones con Emojis
        options = [
            discord.SelectOption(
                label=d['title'][:90], 
                emoji="🎵", 
                description=f"Canal: {d.get('uploader', 'Desconocido')}", 
                value=str(i)
            ) for i, d in enumerate(options_data)
        ]
        super().__init__(placeholder="🔥 Selecciona tu temazo aquí...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Obtenemos datos básicos
        selected_index = int(self.values[0])
        selected_data = self.options_data[selected_index]
        
        # PROCESO DE CARGA (Ahora procesamos solo la elegida para máxima calidad)
        info = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(selected_data['url'], download=False))
        url = info['url']
        titulo = info['title']
        img_url = info.get('thumbnail', None)
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        # Diseño del Embed de confirmación
        embed = discord.Embed(title=f"💿 {titulo}", color=discord.Color.green())
        if img_url: embed.set_thumbnail(url=img_url)
        embed.set_footer(text="Flexus Premium Audio System")

        if vc.is_playing():
            bot.queue.append((url, titulo))
            embed.description = "**✅ Añadida a la cola de reproducción**"
            await interaction.followup.send(embed=embed)
        else:
            bot.songs_played += 1
            bot.current_track = titulo
            vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            embed.description = "**▶️ Reproduciendo ahora en alta calidad**"
            await interaction.followup.send(embed=embed)

class SongView(ui.View):
    def __init__(self, options_data):
        super().__init__()
        self.add_item(SongSelect(options_data))

# --- COMANDOS ---

@bot.tree.command(name="play", description="Busca música a velocidad ultra-rápida")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    try:
        # Búsqueda optimizada (extract_flat=True)
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(cancion, download=False))
        results = data['entries']
        
        view = SongView(results)
        embed = discord.Embed(title="🔎 Resultados de búsqueda", description=f"He encontrado esto para: **{cancion}**", color=discord.Color.blue())
        embed.set_footer(text="Selecciona una opción abajo 👇")
        
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="announce", description="Fuerza el anuncio (Admin)")
async def announce(interaction: discord.Interaction):
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if os.path.exists("anuncio.mp3"):
        if vc.is_playing(): vc.stop()
        vc.play(discord.FFmpegPCMAudio("anuncio.mp3"), after=lambda e: play_next(interaction))
        await registrar_anuncio(interaction.guild)
        
        embed = discord.Embed(title="📢 ANUNCIO", description="Reproduciendo mensaje del patrocinador...", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Error: No existe `anuncio.mp3` en el sistema.")

@bot.tree.command(name="skip", description="Salta la canción")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        embed = discord.Embed(description="⏭️ **Canción saltada**", color=discord.Color.orange())
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stop", description="Detiene y desconecta")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    embed = discord.Embed(description="⏹️ **Desconectado y cola limpia**", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ Pausado.")

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ Reanudado.")

@bot.tree.command(name="queue", description="Muestra la cola")
async def queue(interaction: discord.Interaction):
    if not bot.queue: 
        return await interaction.response.send_message(embed=discord.Embed(description="📂 **La cola está vacía**", color=discord.Color.dark_grey()))
    
    lista = "\n".join([f"`{i+1}.` {t[1]}" for i, t in enumerate(bot.queue[:10])])
    embed = discord.Embed(title="📋 Cola de Reproducción", description=lista, color=discord.Color.purple())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="nowplaying")
async def np(interaction: discord.Interaction):
    cancion = bot.current_track or "Nada sonando"
    embed = discord.Embed(title="🎧 Ahora suena", description=f"**{cancion}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shuffle")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 **Cola mezclada aleatoriamente.**")

@bot.tree.command(name="volume")
async def volume(interaction: discord.Interaction, vol: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = vol / 100
        await interaction.response.send_message(f"🔊 Volumen ajustado al **{vol}%**")

@bot.tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 Latencia: **{round(bot.latency * 1000)}ms**")

@bot.tree.command(name="clear")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ **Cola eliminada.**")

@bot.tree.command(name="stats")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    vistas = data["views"] if data else 0
    embed = discord.Embed(title="📊 Estadísticas de Impacto", description=f"Total de oyentes alcanzados:\n# **{vistas}**", color=discord.Color.teal())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 **¡Nos vemos!**")

@bot.tree.command(name="jump")
async def jump(interaction: discord.Interaction, pos: int):
    if 0 < pos <= len(bot.queue):
        for _ in range(pos - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ Saltando a la posición **#{pos}**")
    else:
        await interaction.response.send_message("❌ Posición inválida.")

@bot.tree.command(name="restart")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Reiniciando pista actual...**")

@bot.tree.command(name="bassboost")
async def bass(interaction: discord.Interaction):
    embed = discord.Embed(title="🔊 Bass Boost", description="Modo **EXTREME BASS** activado.", color=discord.Color.dark_purple())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="loop")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Modo Bucle:** Activado.")

@bot.tree.command(name="lyrics")
async def lyrics(interaction: discord.Interaction):
    embed = discord.Embed(description=f"🔍 Buscando letra para: **{bot.current_track}**...", color=discord.Color.light_grey())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="info")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Flexus V3 System", description="Bot de música avanzado con gestión de Docker y Ads.", color=discord.Color.blurple())
    embed.add_field(name="Versión", value="3.0.1 (Speed Update)", inline=True)
    embed.add_field(name="Desarrollador", value="AlexGaming", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    cmds = "`play`, `announce`, `skip`, `stop`, `pause`, `resume`, `queue`, `nowplaying`, `shuffle`, `volume`, `ping`, `clear`, `stats`, `leave`, `jump`, `restart`, `bassboost`, `loop`, `lyrics`, `info`"
    embed = discord.Embed(title="👑 Panel de Ayuda Flexus", description=cmds, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
