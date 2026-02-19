FROM python:3.10-slim

WORKDIR /app

# Installa dipendenze di sistema utili per CV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente
COPY . .

# Espone la porta del servizio
EXPOSE 8000

# Comando di avvio per FastAPI
CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000"]
