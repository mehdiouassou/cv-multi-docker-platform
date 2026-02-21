import docker
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

@app.exception_handler(docker.errors.DockerException)
async def docker_exception_handler(request: Request, exc: docker.errors.DockerException):
    return JSONResponse(status_code=503, content={"detail": f"Errore demone Docker: {str(exc)}"})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"Errore server interno: {str(exc)}"})

try:
    client = docker.from_env()
except Exception as e:
    print(f"Avviso: client Docker non inizializzato: {e}")
    client = None

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
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    
    try:
        containers = client.containers.list(all=True)
        result = []
        # Preveniamo la visualizzazione/gestione dei container core da UI
        core_containers = ["backend_orchestrator", "frontend_web", "gradio_ui"]
        
        for c in containers:
            # Nascondiamo i container di sistema dalla dashboard per sicurezza
            if any(core in c.name for core in core_containers):
                continue
                
            result.append({
                "id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else "unknown",
                "ports": c.ports
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/containers/{container_id}/start")
def start_container(container_id: str):
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        container.start()
        return {"status": "started", "container_id": container_id}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/containers/{container_id}/stop")
def stop_container(container_id: str):
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        container.stop(timeout=5)
        return {"status": "stopped", "container_id": container_id}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/containers/{container_id}")
def delete_container(container_id: str):
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        container_name = container.name
        # Forza la rimozione anche se in esecuzione (-f)
        container.remove(force=True)
        
        # Pulizia profonda: cerchiamo la cartella su host corrispondente al servizio e la rimuoviamo
        instances_dir = os.path.join(SERVICES_BASE_DIR, "instances")
        try:
            if os.path.exists(instances_dir):
                for folder in os.listdir(instances_dir):
                    folder_path = os.path.join(instances_dir, folder)
                    if os.path.isdir(folder_path):
                        normalized = f"cv_{folder.lower().replace('-', '_')}"
                        if container_name.startswith(normalized + "_"):
                            shutil.rmtree(folder_path)
                            break
        except Exception as cleanup_err:
            print(f"Errore durante l'eliminazione della cartella host: {cleanup_err}")

        return {"status": "deleted", "container_id": container_id}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/containers/{container_id}/stats")
def get_container_stats(container_id: str):
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        if container.status != "running":
            return {"status": container.status, "cpu_percent": 0.0, "mem_percent": 0.0, "uptime": "0s"}
        
        stats = container.stats(stream=False)
        
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        
        number_cpus = stats['cpu_stats'].get('online_cpus', 1)
        cpu_percent = 0.0
        if system_cpu_delta > 0.0 and cpu_delta > 0.0:
            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0
            
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0
        
        started_at = container.attrs['State']['StartedAt']
        
        return {
            "status": container.status,
            "cpu_percent": round(cpu_percent, 2),
            "mem_usage_mb": round(mem_usage / (1024*1024), 2),
            "mem_limit_mb": round(mem_limit / (1024*1024), 2),
            "mem_percent": round(mem_percent, 2),
            "started_at": started_at
        }
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/containers/{container_id}/logs")
def get_container_logs(container_id: str, tail: int = 100):
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        # Preveniamo la visualizzazione dei log dei container core
        core_containers = ["backend_orchestrator", "frontend_web", "gradio_ui"]
        if any(core in container.name for core in core_containers):
             raise HTTPException(status_code=403, detail="Azione vietata sui container di sistema")
             
        logs = container.logs(tail=tail, stdout=True, stderr=True).decode('utf-8', errors='replace')
        return {"logs": logs}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/services/create")
def create_service(req: CreateServiceRequest, background_tasks: BackgroundTasks):
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non connesso.")
        
    source_path = os.path.join(SERVICES_BASE_DIR, req.template_name)
    instances_dir = os.path.join(SERVICES_BASE_DIR, "instances")
    os.makedirs(instances_dir, exist_ok=True)
    target_path = os.path.join(instances_dir, req.service_name)
    
    if not os.path.exists(source_path):
        source_path = os.path.abspath(os.path.join("..", req.template_name))
        target_path = os.path.abspath(os.path.join("..", "instances", req.service_name))
        if not os.path.exists(source_path):
            raise HTTPException(status_code=400, detail=f"Template vuoto o mancante: {req.template_name}")
    
    if os.path.exists(target_path):
        raise HTTPException(status_code=409, detail=f"Errore: Servizio '{req.service_name}' già esistente (directory occupata).")
        
    normalized_name = f"cv_{req.service_name.lower().replace('-', '_')}"
    existing_containers = [c.name for c in client.containers.list(all=True)]
    if any(normalized_name in name for name in existing_containers):
        raise HTTPException(status_code=409, detail=f"Errore: Container basato su '{req.service_name}' già attivo/registrato.")

    try:
        shutil.copytree(source_path, target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore clonazione file di template: {e}")

    background_tasks.add_task(_build_and_run_container, target_path, req, normalized_name)
    
    return {"status": "building", "service_name": req.service_name, "message": "Deploy asincrono in corso."}

def _build_and_run_container(path: str, req: CreateServiceRequest, base_name: str):
    if not client:
        return
        
    try:
        image_name = f"{base_name}:latest"
        client.images.build(path=path, tag=image_name, rm=True)
        
        mem_str = f"{req.mem_limit_mb}m"
        port_binding = {8000: None} # Auto assign per prevenire port clashing
        
        container_name = f"{base_name}_{uuid.uuid4().hex[:6]}"
        
        client.containers.run(
            image_name,
            name=container_name,
            detach=True,
            mem_limit=mem_str,
            nano_cpus=int(req.cpu_cores * 1e9),
            ports=port_binding
        )
    except docker.errors.APIError as e:
        print(f"Docker API Error per {req.service_name}: {e}")
    except Exception as e:
        print(f"Errore imprevisto nel task background: {e}")
