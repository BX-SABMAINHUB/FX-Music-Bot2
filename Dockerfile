FROM python:3.11-slim

# Instalamos FFmpeg para el sonido
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# Comando para encender el bot
CMD ["python", "main.py"]
