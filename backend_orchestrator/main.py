import docker
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import time
import os
import shutil
import uuid

app = FastAPI(title="Backend Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    client = docker.from_env()
except Exception as e:
    print(f"Errore inizializzazione Docker client: {e}")
    client = None

# Base path dove sono memorizzati i template e i servizi
# Se gira in docker, questa cartella deve essere montata dal filesystem host
SERVICES_BASE_DIR = os.environ.get("SERVICES_BASE_DIR", "/projects")

class CreateServiceRequest(BaseModel):
    service_name: str
    template_name: str = "template_service"
    cpu_cores: float = 1.0
    mem_limit_mb: int = 512

@app.get("/health")
def health_check():
    return {"status": "ok", "docker_connected": client is not None}

@app.get("/containers")
def list_containers():
    if not client:
        raise HTTPException(status_code=500, detail="Docker client not available")
    
    # Filtriamo solo i container che fanno parte del nostro sistema
    # (assumiamo che abbiano un label speciale, o filtriamo per prefisso nome)
    containers = client.containers.list(all=True)
    result = []
    for c in containers:
        # Per progetto, ritorniamo tutti i container per semplicità di demo, o solo project specific
        result.append({
            "id": c.short_id,
            "name": c.name,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else "unknown",
            "ports": c.ports
        })
    return result

@app.post("/containers/{container_id}/start")
def start_container(container_id: str):
    try:
        container = client.containers.get(container_id)
        container.start()
        return {"status": "started", "container_id": container_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/containers/{container_id}/stop")
def stop_container(container_id: str):
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=5)
        return {"status": "stopped", "container_id": container_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/containers/{container_id}/stats")
def get_container_stats(container_id: str):
    try:
        container = client.containers.get(container_id)
        if container.status != "running":
            return {"status": container.status, "cpu_percent": 0.0, "mem_percent": 0.0, "uptime": "0s"}
        
        # Recupera le statistiche senza fare stream
        stats = container.stats(stream=False)
        
        # Calcolo CPU
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        
        number_cpus = stats['cpu_stats'].get('online_cpus', 1)
        cpu_percent = 0.0
        if system_cpu_delta > 0.0 and cpu_delta > 0.0:
            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0
            
        # Calcolo Memoria
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        mem_percent = (mem_usage / mem_limit) * 100.0
        
        # Uptime stimato (molto base)
        started_at = container.attrs['State']['StartedAt']
        
        return {
            "status": container.status,
            "cpu_percent": round(cpu_percent, 2),
            "mem_usage_mb": round(mem_usage / (1024*1024), 2),
            "mem_limit_mb": round(mem_limit / (1024*1024), 2),
            "mem_percent": round(mem_percent, 2),
            "started_at": started_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/services/create")
def create_service(req: CreateServiceRequest, background_tasks: BackgroundTasks):
    """
    Copia il template ed esegue il build Docker (simulazione o reale).
    Essendo su Windows e montando directory, copiamo semplicemente la cartella template.
    In produzione reale, avvieremmo un task asincrono per chiamare docker build.
    """
    source_path = os.path.join(SERVICES_BASE_DIR, req.template_name)
    target_path = os.path.join(SERVICES_BASE_DIR, req.service_name)
    
    if not os.path.exists(source_path):
        # Fallback local per test se SERVICES_BASE_DIR non è montato correttamente
        source_path = os.path.abspath(os.path.join("..", req.template_name))
        target_path = os.path.abspath(os.path.join("..", req.service_name))
        
        if not os.path.exists(source_path):
            raise HTTPException(status_code=400, detail=f"Template {req.template_name} non trovato in {source_path}.")
    
    if os.path.exists(target_path):
        raise HTTPException(status_code=400, detail=f"Servizio {req.service_name} esiste già.")
        
    try:
        shutil.copytree(source_path, target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore copia template: {e}")

    # Buildimmagine Docker asincrona
    background_tasks.add_task(_build_and_run_container, target_path, req)
    
    return {"status": "building", "service_name": req.service_name, "message": "Creazione e build in corso."}

def _build_and_run_container(path: str, req: CreateServiceRequest):
    if not client:
        print("Impossibile eseguire build, client Docker non connesso.")
        return
        
    try:
        print(f"Inizio build immagine per {req.service_name} dal path {path}")
        image_name = f"cv_{req.service_name.lower()}:latest"
        client.images.build(path=path, tag=image_name, rm=True)
        print(f"Build {image_name} completata con successo.")
        
        # Avvia il container con i limiti
        mem_str = f"{req.mem_limit_mb}m"
        port_binding = {8000: None} # Mappa una porta host casuale sulla 8000 del container
        
        container = client.containers.run(
            image_name,
            name=f"srv_{req.service_name}_{uuid.uuid4().hex[:6]}",
            detach=True,
            mem_limit=mem_str,
            # cpu_quota = 100000 * cores (dipende da docker su desktop)
            # per semplicità usiamo nano_cpus
            nano_cpus=int(req.cpu_cores * 1e9),
            ports=port_binding
        )
        print(f"Container avviato: {container.name} con limiti CPU {req.cpu_cores} Mem {mem_str}")
        
    except Exception as e:
        print(f"Errore durante build/run background: {e}")
