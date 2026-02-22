import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
import yaml

from service.engine import CVEngine

# Carica configurazione
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
    engine.initialize()
    yield

app = FastAPI(title="CV Service API", lifespan=lifespan)

class HealthResponse(BaseModel):
    status: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Endpoint per il monitoraggio della salute del container.
    """
    # Verifica che il motore sia pronto
    if engine.is_ready():
        return {"status": "ok"}
    raise HTTPException(status_code=503, detail="Service not ready")

@app.get("/info")
async def get_info():
    """
    Restituisce informazioni sul servizio e le sue capacità.
    """
    return {
        "name": config.get("service", {}).get("name"),
        "version": config.get("service", {}).get("version"),
        "description": config.get("service", {}).get("description"),
        "capabilities": engine.get_capabilities()
    }

@app.post("/inference")
async def inference(file: UploadFile = File(...)):
    """
    Esegue l'inferenza sull'immagine fornita.
    """
    try:
        image_bytes = await file.read()
        result = engine.predict(image_bytes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TrainParams(BaseModel):
    epochs: int = 1
    batch_size: int = 32
    learning_rate: float = 0.001
    dataset_name: str = "default_dataset"

@app.post("/train")
async def train(params: TrainParams, background_tasks: BackgroundTasks):
    """
    Avvia il processo di training in background.
    """
    job_id = engine.start_training(params.model_dump(), background_tasks)
    return {"job_id": job_id, "status": "started"}

@app.get("/train/{job_id}")
async def get_train_status(job_id: str):
    """
    Restituisce lo stato del job di training.
    """
    status = engine.get_training_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job non trovato")
    return status
