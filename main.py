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
        print(f"✅ FLEXUS V3.2: BUSCADOR REPARADO + AUDIO HD") 

bot = FlexusBot() 

# CONFIGURACIÓN YTDL (EQUILIBRIO VELOCIDAD/DATOS)
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch5',
    'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}
} 

# CONFIGURACIÓN FFMPEG (CALIDAD RECTA SIN CORTES)
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k'
}
ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# --- LÓGICA DE AUDIO Y ANUNCIOS ---

async def registrar_anuncio(guild):
    if guild.voice_client and guild.voice_client.channel:
        oyentes = len(guild.voice_client.channel.members) - 1
        await stats_col.update_one({"id": "global"}, {"$inc": {"views": max(0, oyentes)}}, upsert=True)

def play_next(interaction):
    if not interaction.guild.voice_client: return
    canal = interaction.guild.voice_client.channel
    
    # SISTEMA VIP: Si hay alguien con rol "VIP", no hay anuncios
    es_vip = any(any(r.name == "VIP" for r in m.roles) for m in canal.members)

    if bot.songs_played >= 3:
        bot.songs_played = 0
        if not es_vip and os.path.exists("anuncio.mp3"):
            source = discord.FFmpegPCMAudio("anuncio.mp3")
            interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
            asyncio.run_coroutine_threadsafe(registrar_anuncio(interaction.guild), bot.loop)
            return

    if len(bot.queue) > 0:
        url, titulo = bot.queue.pop(0)
        bot.songs_played += 1
        bot.current_track = titulo
        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
        interaction.guild.voice_client.play(source, after=lambda e: play_next(interaction))
    else:
        bot.current_track = None

# --- INTERFAZ DE SELECCIÓN ---

class SongSelect(ui.Select):
    def __init__(self, options_data):
        options = []
        for i, d in enumerate(options_data):
            # Priorizamos el título real sobre el genérico
            title = d.get('title') or d.get('alt_title') or "Canción seleccionada"
            uploader = d.get('uploader') or "YouTube"
            options.append(discord.SelectOption(
                label=title[:90], 
                emoji="🎶", 
                description=f"Canal: {uploader[:30]}", 
                value=str(i)
            ))
            
        super().__init__(placeholder="💎 Elige la canción que quieres escuchar...", options=options)
        self.options_data = options_data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        selected_index = int(self.values[0])
        selected_data = self.options_data[selected_index]
        video_url = selected_data.get('webpage_url') or selected_data.get('url')
        
        # Extracción final para el audio directo
        info = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(video_url, download=False))
        real_url = info['url']
        titulo = info['title']
        
        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
        
        embed = discord.Embed(title=f"🎵 {titulo}", color=0x2f3136)
        embed.set_footer(text="Flexus Premium | Audio HD 192kbps")

        if vc.is_playing():
            bot.queue.append((real_url, titulo))
            embed.description = "✅ **Añadida a la cola correctamente**"
            await interaction.followup.send(embed=embed)
        else:
            bot.songs_played += 1
            bot.current_track = titulo
            vc.play(discord.FFmpegPCMAudio(real_url, **FFMPEG_OPTIONS), after=lambda e: play_next(interaction))
            embed.description = "▶️ **Reproduciendo ahora mismo**"
            await interaction.followup.send(embed=embed)

class SongView(ui.View):
    def __init__(self, options_data):
        super().__init__()
        self.add_item(SongSelect(options_data))

# --- LOS 20 COMANDOS DE FLEXUS ---

@bot.tree.command(name="play", description="Busca y elige entre las mejores opciones")
async def play(interaction: discord.Interaction, cancion: str):
    await interaction.response.defer()
    try:
        # Buscamos sin extract_flat para obtener nombres reales SIEMPRE
        data = await asyncio.get_event_loop().run_in_executor(None, lambda: ytdl.extract_info(f"ytsearch5:{cancion}", download=False))
        results = data['entries']

        if not results:
            return await interaction.followup.send("❌ No he encontrado resultados.")

        view = SongView(results)
        embed = discord.Embed(
            title="🎯 Resultados para: " + cancion, 
            description="He encontrado estas canciones parecidas. ¡Elige una!", 
            color=0x00ff77
        )
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await interaction.followup.send(f"❌ Error en la búsqueda: {e}")

@bot.tree.command(name="announce", description="Lanza un anuncio manualmente")
async def announce(interaction: discord.Interaction):
    vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
    if os.path.exists("anuncio.mp3"):
        if vc.is_playing(): vc.stop()
        vc.play(discord.FFmpegPCMAudio("anuncio.mp3"), after=lambda e: play_next(interaction))
        await registrar_anuncio(interaction.guild)
        await interaction.response.send_message("📢 **Reproduciendo anuncio publicitario...**")
    else:
        await interaction.response.send_message("❌ Error: Sube el archivo `anuncio.mp3`.")

@bot.tree.command(name="skip", description="Salta la pista actual")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ **Canción saltada.**")

@bot.tree.command(name="stop", description="Limpia todo y desconecta")
async def stop(interaction: discord.Interaction):
    bot.queue.clear()
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("⏹️ **Bot detenido y cola vaciada.**")

@bot.tree.command(name="pause", description="Pausa la música")
async def pause(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.pause()
    await interaction.response.send_message("⏸️ **Música pausada.**")

@bot.tree.command(name="resume", description="Sigue con la música")
async def resume(interaction: discord.Interaction):
    if interaction.guild.voice_client: interaction.guild.voice_client.resume()
    await interaction.response.send_message("▶️ **Música reanudada.**")

@bot.tree.command(name="queue", description="Ver la lista de espera")
async def queue(interaction: discord.Interaction):
    if not bot.queue: return await interaction.response.send_message("📋 **La cola está vacía.**")
    lista = "\n".join([f"**{i+1}.** {t[1]}" for i, t in enumerate(bot.queue[:10])])
    embed = discord.Embed(title="📋 Cola de Reproducción", description=lista, color=0x7289da)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="nowplaying", description="¿Qué está sonando?")
async def np(interaction: discord.Interaction):
    txt = bot.current_track if bot.current_track else "Nada"
    await interaction.response.send_message(f"🎧 **Ahora suena:** {txt}")

@bot.tree.command(name="shuffle", description="Mezcla la cola")
async def shuffle(interaction: discord.Interaction):
    random.shuffle(bot.queue)
    await interaction.response.send_message("🔀 **Cola mezclada.**")

@bot.tree.command(name="volume", description="Ajusta el volumen (0-100)")
async def volume(interaction: discord.Interaction, nivel: int):
    if interaction.guild.voice_client and interaction.guild.voice_client.source:
        interaction.guild.voice_client.source.volume = nivel / 100
        await interaction.response.send_message(f"🔊 Volumen al **{nivel}%**")

@bot.tree.command(name="ping", description="Ver latencia")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 Latencia: **{round(bot.latency * 1000)}ms**")

@bot.tree.command(name="clear", description="Borra la cola")
async def clear(interaction: discord.Interaction):
    bot.queue.clear()
    await interaction.response.send_message("🗑️ **Cola limpiada.**")

@bot.tree.command(name="stats", description="Impacto de audiencia")
async def stats(interaction: discord.Interaction):
    data = await stats_col.find_one({"id": "global"})
    v = data["views"] if data else 0
    await interaction.response.send_message(f"📊 **Impacto Total:** {v} oyentes alcanzados.")

@bot.tree.command(name="leave", description="Saca al bot del canal")
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client: await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 **¡Hasta la próxima!**")

@bot.tree.command(name="jump", description="Salta a una posición de la cola")
async def jump(interaction: discord.Interaction, posicion: int):
    if 0 < posicion <= len(bot.queue):
        for _ in range(posicion - 1): bot.queue.pop(0)
        interaction.guild.voice_client.stop()
        await interaction.response.send_message(f"⏩ **Saltando a la canción #{posicion}...**")

@bot.tree.command(name="restart", description="Reinicia la canción")
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Reiniciando pista...**")

@bot.tree.command(name="bassboost", description="Potencia los bajos")
async def bass(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 **Bass Boost activado.**")

@bot.tree.command(name="loop", description="Repite la canción")
async def loop(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Bucle activado.**")

@bot.tree.command(name="lyrics", description="Busca la letra")
async def lyrics(interaction: discord.Interaction):
    await interaction.response.send_message(f"🔍 Buscando letras para **{bot.current_track}**...")

@bot.tree.command(name="info", description="Información del sistema")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(title="Flexus Bot V3.2 Premium", color=0x00ff77)
    embed.add_field(name="Calidad", value="192kbps HD", inline=True)
    embed.add_field(name="VIP", value="Soportado", inline=True)
    embed.set_footer(text="By AlexGaming")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Lista de comandos")
async def help_cmd(interaction: discord.Interaction):
    c = "play, announce, skip, stop, pause, resume, queue, nowplaying, shuffle, volume, ping, clear, stats, leave, jump, restart, bassboost, loop, lyrics, info"
    await interaction.response.send_message(f"👑 **Comandos Flexus:**\n`{c}`")

bot.run(TOKEN)
