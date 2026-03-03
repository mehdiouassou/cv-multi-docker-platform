"""
Backend Orchestrator - Centro di controllo della piattaforma Symphony.

Questo modulo implementa l'API REST che gestisce il ciclo di vita dei container
Docker sulla macchina host. Usa la libreria docker-py per comunicare col Docker
daemon attraverso il socket Unix montato come volume nel docker-compose.

Funzionalita principali:
- Listare, avviare, fermare, eliminare container
- Leggere statistiche in tempo reale (CPU, RAM)
- Leggere i log di un container
- Creare nuovi servizi CV partendo dal template_service
"""

import docker
import httpx
import json
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import time
import os
import shutil
import uuid

app = FastAPI(title="Backend Orchestrator")

# CORS aperto perche' frontend e backend girano su porte diverse (80 e 8080).
# In un contesto Docker interno questo non crea problemi di sicurezza.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Handler globali per le eccezioni Docker e generiche.
# Cosi se qualcosa va storto col daemon Docker l'utente riceve un 503 pulito
# invece di un errore 500 generico.
@app.exception_handler(docker.errors.DockerException)
async def docker_exception_handler(request: Request, exc: docker.errors.DockerException):
    return JSONResponse(status_code=503, content={"detail": f"Errore demone Docker: {str(exc)}"})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"Errore server interno: {str(exc)}"})

# Connessione al Docker daemon. Se fallisce (es. durante i test senza Docker)
# il client viene settato a None e gli endpoint restituiscono 503.
try:
    client = docker.from_env()
except Exception as e:
    print(f"Avviso: client Docker non inizializzato: {e}")
    client = None

# Percorso base dove cercare i template e dove creare le istanze dei nuovi servizi.
# In Docker e' /projects (montato dal docker-compose), in locale punta alla root del repo.
SERVICES_BASE_DIR = os.environ.get("SERVICES_BASE_DIR", "/projects")


class CreateServiceRequest(BaseModel):
    """Schema della richiesta per creare un nuovo servizio da template."""
    service_name: str
    template_name: str = "template_service"
    cpu_cores: float = 1.0
    mem_limit_mb: int = 512


@app.get("/health")
def health_check():
    """Restituisce lo stato del backend e se la connessione a Docker e' attiva."""
    return {"status": "ok", "docker_connected": client is not None}


PLATFORM_LABEL = "symphony.managed"
META_FILENAME = ".symphony_meta.json"

@app.get("/containers")
def list_containers():
    """
    Elenca solo i container gestiti dalla piattaforma Symphony.

    Il filtro funziona in due modi:
    - I container creati via /services/create hanno il label symphony.managed=true
    - Il container trashnet di default (da docker-compose) viene riconosciuto per nome
    I container di sistema (backend, frontend, gradio) sono sempre esclusi.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")

    try:
        containers = client.containers.list(all=True)
        result = []
        core_containers = ["backend_orchestrator", "frontend_web", "gradio_ui"]

        for c in containers:
            if any(core in c.name for core in core_containers):
                continue

            # Mostra solo i container della piattaforma:
            # 1) quelli con il label symphony.managed (creati da template)
            # 2) quelli il cui nome contiene "trashnet" (servizio di default)
            # 3) quelli il cui nome inizia con "cv_" (convenzione della piattaforma)
            is_managed = c.labels.get(PLATFORM_LABEL) == "true"
            is_trashnet = "trashnet" in c.name
            is_cv_service = c.name.startswith("cv_")

            if not (is_managed or is_trashnet or is_cv_service):
                continue

            result.append({
                "id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": (c.image.tags[0] if c.image and c.image.tags else c.attrs.get("Config", {}).get("Image", "unknown")),
                "ports": c.ports
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/containers/{container_id}/start")
def start_container(container_id: str):
    """Avvia un container fermo. Prende l'id corto del container."""
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
    """Ferma un container in esecuzione. Timeout di 5 secondi prima del kill forzato."""
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


@app.post("/containers/{container_id}/restart")
def restart_container(container_id: str):
    """
    Riavvia un container (equivalente a stop + start in sequenza).
    Timeout di 5 secondi prima del kill forzato durante lo stop.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        container.restart(timeout=5)
        return {"status": "restarted", "container_id": container_id}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/containers/{container_id}")
def delete_container(container_id: str):
    """
    Elimina un container (anche se sta girando, con force=True).

    Dopo l'eliminazione, cerca nella cartella instances/ la directory
    corrispondente al servizio e la rimuove per pulire il filesystem.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        container_name = container.name
        container.remove(force=True)

        # Pulizia della cartella sorgente del servizio su disco
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
    """
    Legge le statistiche di CPU e RAM di un container in tempo reale.

    La percentuale CPU viene calcolata cosi:
    - cpu_delta = differenza di utilizzo CPU tra la misura corrente e la precedente
    - system_delta = differenza di utilizzo CPU di sistema nello stesso intervallo
    - cpu_percent = (cpu_delta / system_delta) * numero_core * 100

    La RAM e' letta direttamente da memory_stats (usage e limit in bytes).
    Se il container non sta girando, ritorna tutto a zero.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        if container.status != "running":
            return {"status": container.status, "cpu_percent": 0.0, "mem_percent": 0.0, "uptime": "0s"}

        stats = container.stats(stream=False)

        # Calcolo percentuale CPU dal delta tra due misurazioni consecutive
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']

        number_cpus = stats['cpu_stats'].get('online_cpus', 1)
        cpu_percent = 0.0
        if system_cpu_delta > 0.0 and cpu_delta > 0.0:
            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0

        # Lettura RAM in bytes, convertita in MB per la risposta.
        # HostConfig['Memory'] == 0 significa nessun limite esplicito impostato:
        # in quel caso Docker riporta la RAM totale dell'host come "limite", che
        # non e' un vero limite. Lo comunichiamo esplicitamente col campo has_mem_limit.
        mem_usage = stats['memory_stats'].get('usage', 0)
        mem_limit = stats['memory_stats'].get('limit', 1)
        host_config_mem = container.attrs.get('HostConfig', {}).get('Memory', 0)
        has_mem_limit = host_config_mem > 0
        mem_percent = (mem_usage / mem_limit) * 100.0 if (has_mem_limit and mem_limit > 0) else 0.0

        started_at = container.attrs['State']['StartedAt']

        return {
            "status": container.status,
            "cpu_percent": round(cpu_percent, 2),
            "mem_usage_mb": round(mem_usage / (1024*1024), 2),
            "mem_limit_mb": round(mem_limit / (1024*1024), 2) if has_mem_limit else None,
            "has_mem_limit": has_mem_limit,
            "mem_percent": round(mem_percent, 2),
            "started_at": started_at
        }
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/containers/{container_id}/logs")
def get_container_logs(container_id: str, tail: int = 100):
    """
    Restituisce le ultime N righe di log (stdout + stderr) di un container.
    I container di sistema sono protetti e restituiscono 403.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        core_containers = ["backend_orchestrator", "frontend_web", "gradio_ui"]
        if any(core in container.name for core in core_containers):
             raise HTTPException(status_code=403, detail="Azione vietata sui container di sistema")

        logs = container.logs(tail=tail, stdout=True, stderr=True).decode('utf-8', errors='replace')
        return {"logs": logs}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_instance_path(service_name: str):
    """Risolve il percorso della cartella di un servizio in instances/."""
    instances_dir = os.path.join(SERVICES_BASE_DIR, "instances")
    target_path = os.path.join(instances_dir, service_name)
    if os.path.exists(target_path):
        return target_path, instances_dir
    # Fallback path relativo
    target_path = os.path.abspath(os.path.join("..", "instances", service_name))
    instances_dir = os.path.dirname(target_path)
    if os.path.exists(target_path):
        return target_path, instances_dir
    return None, None


@app.post("/services/create")
def create_service(req: CreateServiceRequest):
    """
    Step 1: copia il template in instances/{nome_servizio}.

    NON builda ne avvia il container. L'utente deve prima modificare
    algorithm.py, config.yaml e requirements.txt, poi chiamare
    POST /services/{nome}/build per avviare il build.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non connesso.")

    source_path = os.path.join(SERVICES_BASE_DIR, req.template_name)
    instances_dir = os.path.join(SERVICES_BASE_DIR, "instances")
    target_path = os.path.join(instances_dir, req.service_name)

    if not os.path.exists(source_path):
        source_path = os.path.abspath(os.path.join("..", req.template_name))
        target_path = os.path.abspath(os.path.join("..", "instances", req.service_name))
        instances_dir = os.path.dirname(target_path)
        if not os.path.exists(source_path):
            raise HTTPException(status_code=400, detail=f"Template vuoto o mancante: {req.template_name}")

    os.makedirs(instances_dir, exist_ok=True)

    if os.path.exists(target_path):
        raise HTTPException(status_code=409, detail=f"Errore: Servizio '{req.service_name}' gia' esistente (directory occupata).")

    normalized_name = f"cv_{req.service_name.lower().replace('-', '_')}"
    existing_containers = [c.name for c in client.containers.list(all=True)]
    if any(normalized_name in name for name in existing_containers):
        raise HTTPException(status_code=409, detail=f"Errore: Container basato su '{req.service_name}' gia' attivo/registrato.")

    try:
        shutil.copytree(source_path, target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore clonazione file di template: {e}")

    # Scrivi metadata per tracciare lo stato del servizio
    meta = {
        "service_name": req.service_name,
        "template_name": req.template_name,
        "cpu_cores": req.cpu_cores,
        "mem_limit_mb": req.mem_limit_mb,
        "status": "pending_setup",
        "created_at": datetime.now().isoformat()
    }
    with open(os.path.join(target_path, META_FILENAME), "w") as f:
        json.dump(meta, f, indent=2)

    return {
        "status": "pending_setup",
        "service_name": req.service_name,
        "files_to_edit": [
            f"instances/{req.service_name}/service/impl/algorithm.py",
            f"instances/{req.service_name}/config.yaml",
            f"instances/{req.service_name}/requirements.txt"
        ],
        "message": "Template copiato. Modifica i file e poi clicca Build & Deploy."
    }


@app.post("/services/{service_name}/build")
def build_service(service_name: str, background_tasks: BackgroundTasks):
    """
    Step 2: builda l'immagine Docker e avvia il container.

    Chiamato dopo che l'utente ha modificato i file del servizio.
    Legge i parametri dal file .symphony_meta.json creato allo step 1.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non connesso.")

    target_path, _ = _resolve_instance_path(service_name)
    if not target_path:
        raise HTTPException(status_code=404, detail=f"Servizio '{service_name}' non trovato.")

    meta_path = os.path.join(target_path, META_FILENAME)
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=400, detail="File metadata mancante.")

    with open(meta_path) as f:
        meta = json.load(f)

    if meta["status"] not in ("pending_setup", "build_failed"):
        raise HTTPException(status_code=409, detail=f"Servizio in stato '{meta['status']}', non buildabile.")

    meta["status"] = "building"
    meta.pop("error", None)
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    normalized_name = f"cv_{service_name.lower().replace('-', '_')}"
    req = CreateServiceRequest(
        service_name=meta["service_name"],
        template_name=meta["template_name"],
        cpu_cores=meta["cpu_cores"],
        mem_limit_mb=meta["mem_limit_mb"]
    )

    background_tasks.add_task(_build_and_run_container, target_path, req, normalized_name, meta_path)
    return {"status": "building", "service_name": service_name, "message": "Build avviato."}


@app.get("/services/pending")
def list_pending_services():
    """Elenca i servizi creati ma non ancora deployati (in attesa di setup o build)."""
    results = []
    for base in [os.path.join(SERVICES_BASE_DIR, "instances"),
                 os.path.abspath(os.path.join("..", "instances"))]:
        if not os.path.exists(base):
            continue
        for folder in os.listdir(base):
            folder_path = os.path.join(base, folder)
            meta_path = os.path.join(folder_path, META_FILENAME)
            if not os.path.isdir(folder_path) or not os.path.exists(meta_path):
                continue
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                if meta.get("status") in ("pending_setup", "building", "build_failed"):
                    results.append({
                        "service_name": meta["service_name"],
                        "status": meta["status"],
                        "created_at": meta.get("created_at"),
                        "cpu_cores": meta.get("cpu_cores", 1.0),
                        "mem_limit_mb": meta.get("mem_limit_mb", 512),
                        "error": meta.get("error"),
                        "files_to_edit": [
                            f"instances/{folder}/service/impl/algorithm.py",
                            f"instances/{folder}/config.yaml",
                            f"instances/{folder}/requirements.txt"
                        ]
                    })
            except (json.JSONDecodeError, KeyError):
                continue
        break  # Usa solo il primo path valido
    return results


@app.delete("/services/{service_name}")
def delete_pending_service(service_name: str):
    """Elimina un servizio non ancora deployato (rimuove la cartella da instances/)."""
    target_path, _ = _resolve_instance_path(service_name)
    if not target_path:
        raise HTTPException(status_code=404, detail=f"Servizio '{service_name}' non trovato.")
    shutil.rmtree(target_path)
    return {"status": "deleted", "service_name": service_name}


def _update_meta(meta_path: str, updates: dict):
    """Aggiorna i campi nel file .symphony_meta.json."""
    if not meta_path or not os.path.exists(meta_path):
        return
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        meta.update(updates)
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass


def _build_and_run_container(path: str, req: CreateServiceRequest, base_name: str, meta_path: str = None):
    """
    Task in background: builda l'immagine Docker e avvia il container.

    - L'immagine viene taggata come {base_name}:latest
    - Il container ha un nome univoco con suffisso UUID per evitare collisioni
    - CPU e RAM sono limitati secondo i parametri della richiesta
    - La porta 8000 viene mappata automaticamente su una porta libera dell'host
    - Se meta_path e' fornito, aggiorna lo stato nel file metadata
    """
    if not client:
        return

    try:
        image_name = f"{base_name}:latest"
        client.images.build(path=path, tag=image_name, rm=True)

        mem_str = f"{req.mem_limit_mb}m"
        port_binding = {8000: None}

        container_name = f"{base_name}_{uuid.uuid4().hex[:6]}"

        client.containers.run(
            image_name,
            name=container_name,
            detach=True,
            mem_limit=mem_str,
            nano_cpus=int(req.cpu_cores * 1e9),
            ports=port_binding,
            labels={PLATFORM_LABEL: "true"}
        )
        _update_meta(meta_path, {"status": "deployed"})
    except docker.errors.APIError as e:
        print(f"Docker API Error per {req.service_name}: {e}")
        _update_meta(meta_path, {"status": "build_failed", "error": str(e)})
    except Exception as e:
        print(f"Errore imprevisto nel task background: {e}")
        _update_meta(meta_path, {"status": "build_failed", "error": str(e)})


def _get_container_internal_url(container_id: str) -> str:
    """
    Dato un container_id, trova l'IP interno nella rete Docker e restituisce
    l'URL base del servizio (es. http://172.17.0.5:8000).

    L'orchestrator gira nella stessa rete Docker dei servizi CV, quindi puo
    raggiungerli direttamente via IP interno senza passare per le porte host.
    Questo evita problemi di CORS perche' le chiamate partono dal backend,
    non dal browser.
    """
    if not client:
        raise HTTPException(status_code=503, detail="Docker client non disponibile")
    try:
        container = client.containers.get(container_id)
        if container.status != "running":
            raise HTTPException(status_code=400, detail="Container non in esecuzione")

        # Prende l'IP interno dal primo network disponibile
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        for net_name, net_info in networks.items():
            ip = net_info.get("IPAddress")
            if ip:
                return f"http://{ip}:8000"

        raise HTTPException(status_code=500, detail="IP interno del container non trovato")
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} non trovato")


@app.get("/containers/{container_id}/health")
def proxy_health(container_id: str):
    """
    Proxy per l'endpoint GET /health del servizio CV.

    Il frontend non puo chiamare direttamente i servizi CV perche' mancano
    gli header CORS. Questo endpoint fa da ponte: l'orchestrator chiama il
    servizio internamente via rete Docker e restituisce il risultato.
    """
    base_url = _get_container_internal_url(container_id)
    try:
        with httpx.Client(timeout=3.0) as http:
            res = http.get(f"{base_url}/health")
            return res.json()
    except Exception:
        return {"status": "unreachable"}


@app.get("/containers/{container_id}/info")
def proxy_info(container_id: str):
    """
    Proxy per l'endpoint GET /info del servizio CV.

    Restituisce le capabilities del servizio (nome algoritmo, classi supportate, ecc).
    Il frontend usa queste info per decidere se mostrare la sezione di inferenza.
    """
    base_url = _get_container_internal_url(container_id)
    try:
        with httpx.Client(timeout=3.0) as http:
            res = http.get(f"{base_url}/info")
            return res.json()
    except Exception:
        return {"error": "Servizio non raggiungibile"}


@app.post("/containers/{container_id}/inference")
async def proxy_inference(container_id: str, file: UploadFile = File(...)):
    """
    Proxy per l'endpoint POST /inference del servizio CV.

    Riceve l'immagine dal frontend, la inoltra al servizio CV interno
    via rete Docker e restituisce il risultato della classificazione.
    """
    base_url = _get_container_internal_url(container_id)
    try:
        file_bytes = await file.read()
        with httpx.Client(timeout=30.0) as http:
            res = http.post(
                f"{base_url}/inference",
                files={"file": (file.filename or "image.png", file_bytes, file.content_type or "image/png")}
            )
            if res.status_code != 200:
                raise HTTPException(status_code=res.status_code, detail="Errore dal servizio CV")
            return res.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout: il servizio CV non ha risposto in tempo")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore proxy inferenza: {str(e)}")
