@bot.tree.command(name="play", description="Reproduce música")
async def play(interaction: discord.Interaction, busqueda: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("❌ ¡Entra a un canal de voz!", ephemeral=True)

    await interaction.response.defer()
    
    try:
        # Forzamos opciones que evitan que YouTube nos bloquee
        ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{busqueda}", download=False)['entries'][0]
            url = info['url']
            titulo = info['title']

        vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()

        # Usamos opciones de reconexión para que el audio no se corte
        audio_source = discord.FFmpegPCMAudio(url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn")
        
        if vc.is_playing():
            vc.stop()
            
        vc.play(audio_source)
        await interaction.followup.send(f"🎶 Reproduciendo: **{titulo}**")

    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send(f"❌ Error: No se pudo cargar el audio. Verifica que FFmpeg esté instalado.")
