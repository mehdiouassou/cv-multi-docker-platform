"""
API FastAPI del servizio di Computer Vision.

Questo modulo definisce gli endpoint REST che ogni servizio CV deve implementare
secondo il contratto della piattaforma Symphony:
- GET /health    -> stato del servizio
- GET /info      -> metadati e capabilities
- POST /inference -> classificazione immagine
- POST /train    -> avvio training in background
- GET /train/{id} -> stato del training

La configurazione viene letta dal file config.yaml nella root del servizio.
L'engine viene inizializzato all'avvio del container tramite il pattern lifespan
di FastAPI (che sostituisce il vecchio on_event("startup") deprecato).
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
import yaml

from service.engine import CVEngine

# Carica la configurazione dal file YAML (nome servizio, versione, ecc)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.environ.get("CONFIG_PATH", os.path.join(base_dir, "config.yaml"))
try:
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"Errore nel caricamento della configurazione: {e}")
    config = {"service": {"name": "Unknown", "version": "0.0.0"}}

engine = CVEngine(config)


@asynccontextmanager
async def lifespan(app):
    """
    Lifespan di FastAPI: il codice prima del yield viene eseguito all'avvio,
    quello dopo allo shutdown. Qui carichiamo il modello in memoria.
    """
    engine.initialize()
    yield


app = FastAPI(title="CV Service API", lifespan=lifespan)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Verifica se il modello e' caricato e il servizio e' pronto a ricevere richieste."""
    if engine.is_ready():
        return {"status": "ok"}
    raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/info")
async def get_info():
    """Restituisce nome, versione, descrizione e capabilities del servizio."""
    return {
        "name": config.get("service", {}).get("name"),
        "version": config.get("service", {}).get("version"),
        "description": config.get("service", {}).get("description"),
        "capabilities": engine.get_capabilities()
    }


@app.post("/inference")
async def inference(file: UploadFile = File(...)):
    """
    Riceve un'immagine via multipart/form-data e restituisce la classificazione.

    L'immagine viene letta come bytes e passata all'engine che la preprocessa
    e la passa al modello. Restituisce risultato, confidence e latenza.
    """
    try:
        image_bytes = await file.read()
        result = engine.predict(image_bytes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TrainParams(BaseModel):
    """Parametri per il training. Tutti hanno valori di default."""
    epochs: int = 1
    batch_size: int = 32
    learning_rate: float = 0.001
    dataset_name: str = "default_dataset"


@app.post("/train")
async def train(params: TrainParams, background_tasks: BackgroundTasks):
    """
    Avvia il fine-tuning del modello in background.

    Non blocca la risposta HTTP: restituisce subito un job_id che il client
    puo usare per controllare lo stato del training con GET /train/{job_id}.
    """
    job_id = engine.start_training(params.model_dump(), background_tasks)
    return {"job_id": job_id, "status": "started"}


@app.get("/train/{job_id}")
async def get_train_status(job_id: str):
    """Restituisce lo stato del job di training (running, completed, failed + metriche)."""
    status = engine.get_training_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job non trovato")
    return status
