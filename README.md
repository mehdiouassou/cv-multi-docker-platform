# Symphony: Piattaforma Multi-Docker per Computer Vision

[![CI](https://github.com/mehdiouassou/cv-multi-docker-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/mehdiouassou/cv-multi-docker-platform/actions/workflows/ci.yml)
[![Docker Hub - Backend](https://img.shields.io/docker/image-size/ouassou/cv-backend-orchestrator/latest?label=backend)](https://hub.docker.com/r/ouassou/cv-backend-orchestrator)
[![Docker Hub - TrashNet](https://img.shields.io/docker/image-size/ouassou/cv-service-trashnet/latest?label=trashnet)](https://hub.docker.com/r/ouassou/cv-service-trashnet)
[![Docker Hub - Frontend](https://img.shields.io/docker/image-size/ouassou/cv-frontend-web/latest?label=frontend)](https://hub.docker.com/r/ouassou/cv-frontend-web)

## Cos'e' questo progetto

Symphony e' una piattaforma che permette di gestire piu container Docker, ognuno dei quali contiene un algoritmo di Computer Vision indipendente. Dalla dashboard web si possono avviare, fermare, eliminare e monitorare i container, e anche crearne di nuovi partendo da un template.

Il progetto include un servizio di classificazione rifiuti (TrashNet) basato su MobileNetV2 come esempio funzionante, ma la piattaforma e' pensata per ospitare qualsiasi tipo di algoritmo CV (detection, segmentation, anomaly detection, ecc). Basta clonare il template e implementare il proprio algoritmo.

## Cosa serve per farlo funzionare

- **Docker Engine** versione 24 o superiore (oppure Docker Desktop su Windows/Mac)
- **Docker Compose** (incluso in Docker Desktop, altrimenti va installato a parte)
- **Python 3.10+** serve solo se vuoi eseguire i test o il notebook EDA fuori da Docker. Per il funzionamento normale basta Docker.

## Come installare e avviare

```bash
# 1. Clona il repository
git clone https://github.com/mehdiouassou/cv-multi-docker-platform.git
cd cv-multi-docker-platform

# 2. Builda tutte le immagini Docker (ci mette un po' la prima volta
#    perche' deve scaricare PyTorch, Node.js, ecc)
docker compose build

# 3. Avvia tutti i servizi in background
docker compose up -d

# 4. Controlla che siano tutti running
docker compose ps
```

Dopo qualche secondo i servizi saranno pronti. Per fermare tutto:
```bash
docker compose down
```

### Dove accedere

| Componente | URL | Descrizione |
|---|---|---|
| Dashboard Frontend | http://localhost | Interfaccia web per gestire i container |
| API Orchestratore | http://localhost:8080/docs | Swagger UI con tutti gli endpoint del backend |
| API Servizio TrashNet | http://localhost:8000/docs | Swagger UI del servizio di classificazione |
| Interfaccia Gradio | http://localhost:7860 | Upload immagini e webcam per test rapidi |

---

## Architettura del sistema

Il sistema e' composto da 5 servizi Docker che comunicano tra loro tramite la rete interna di Docker Compose:

```
                    +-------------------+
                    |   Frontend Web    |  <-- porta 80
                    |  (React + Nginx)  |      L'utente interagisce da qui
                    +--------+----------+
                             |
                             | HTTP (polling ogni 3s)
                             |
                    +--------v----------+
                    |    Backend         |  <-- porta 8080
                    |   Orchestrator    |      Gestisce tutti i container
                    |    (FastAPI)      |      tramite Docker SDK
                    +--------+----------+
                             |
                    Docker Socket (/var/run/docker.sock)
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v-------+
     | TrashNet   |  | Servizio N  |  |  Gradio UI |
     | Classifier |  | (da templ.) |  |  (test)    |
     | porta 8000 |  | porta auto  |  | porta 7860 |
     +------------+  +-------------+  +------------+
```

### Come comunicano i componenti

1. Il **frontend** fa polling ogni 3 secondi verso `GET /containers` del backend per aggiornare la lista dei container e le statistiche
2. Il **backend orchestrator** usa la libreria `docker-py` (SDK Docker ufficiale per Python) per parlare col Docker daemon della macchina host, attraverso il socket montato come volume
3. Ogni **servizio CV** e' indipendente e risponde sulla propria porta. Il backend lo raggiunge tramite l'API Docker per leggere stats e logs
4. L'interfaccia **Gradio** e' opzionale e parla direttamente col servizio CV per fare inferenza

---

## Struttura delle cartelle

```
cv-multi-docker-platform/
|
|-- backend_orchestrator/          # Centro di controllo
|   |-- main.py                    # API FastAPI: tutti gli endpoint di gestione
|   |-- test_main.py               # Test unitari del backend
|   |-- requirements.txt           # Dipendenze Python: fastapi, docker-py, ecc
|   |-- Dockerfile                 # Immagine Docker del backend
|   +-- __init__.py
|
|-- cv_service_trashnet/           # Servizio CV di esempio (classificazione rifiuti)
|   |-- config.yaml                # Configurazione: nome servizio, versione, task
|   |-- test_cv_service.py         # Test unitari del servizio
|   |-- requirements.txt           # Dipendenze: pytorch, torchvision, datasets, ecc
|   |-- Dockerfile                 # Immagine Docker con dipendenze OpenCV
|   +-- service/
|       |-- main.py                # API FastAPI: /health, /info, /inference, /train
|       |-- engine.py              # CVEngine: fa da ponte tra API e algoritmo
|       +-- impl/
|           +-- algorithm.py       # BaseAlgorithm: modello MobileNetV2, training, inferenza
|
|-- template_service/              # Template per creare nuovi servizi
|   |-- (stessa struttura di cv_service_trashnet, ma con algoritmo placeholder)
|
|-- frontend_web/                  # Dashboard React
|   |-- package.json               # Dipendenze: react, tailwind, framer-motion, lucide
|   |-- Dockerfile                 # Build multi-stage: Node per compilare, Nginx per servire
|   |-- vite.config.ts             # Configurazione bundler Vite
|   +-- src/
|       |-- App.tsx                # Componente principale: dashboard, modali, polling
|       |-- main.tsx               # Entry point React
|       +-- index.css              # Stili base e scrollbar custom
|
|-- gradio_ui/                     # Interfaccia Gradio (opzionale)
|   |-- app.py                     # Upload immagine/webcam + chiamata inferenza
|   +-- Dockerfile
|
|-- eda/                           # Exploratory Data Analysis
|   +-- eda.ipynb                  # Notebook: distribuzione classi, campioni visivi
|
|-- .github/workflows/
|   +-- ci.yml                     # Pipeline CI/CD: test, lint, docker build, push
|
|-- docker-compose.yml             # Definizione di tutti i servizi e volumi
|-- setup.py                       # Package Python installabile con pip
+-- .gitignore                     # Esclude venv, data, __pycache__, ecc
```

---

## Spiegazione dettagliata dei componenti

### 1. Backend Orchestrator (`backend_orchestrator/main.py`)

E' il cervello del sistema. Un'API FastAPI che comunica col Docker daemon per gestire i container.

**Come funziona:**
- All'avvio, prova a connettersi al Docker daemon con `docker.from_env()`. Se non riesce (tipo se stai eseguendo i test senza Docker), salva `client = None` e gli endpoint che richiedono Docker restituiscono 503.
- I container di sistema (backend_orchestrator, frontend_web, gradio_ui) vengono nascosti dalla lista e non possono essere fermati o eliminati dalla dashboard, per evitare che l'utente si spenga il sistema da solo.

**Endpoint disponibili:**

`GET /health` restituisce `{"status": "ok", "docker_connected": true/false}`. Serve per sapere se il backend e' vivo e se Docker e' raggiungibile.

`GET /containers` elenca tutti i container Docker attivi sulla macchina, escludendo quelli di sistema. Per ogni container restituisce id, nome, stato (running/exited), immagine e porte.

`POST /containers/{id}/start` e `POST /containers/{id}/stop` avviano o fermano un container specifico. Lo stop ha un timeout di 5 secondi.

`DELETE /containers/{id}` rimuove un container (con force, anche se sta girando). Dopo la rimozione, cerca e cancella anche la cartella sorgente nella directory `instances/` se il servizio era stato creato da template.

`GET /containers/{id}/stats` legge le statistiche in tempo reale dal Docker daemon. Calcola la percentuale CPU confrontando il delta di utilizzo tra due misurazioni consecutive (`cpu_delta / system_cpu_delta * num_cpus * 100`). Per la RAM legge direttamente `memory_stats.usage` e `memory_stats.limit`.

`GET /containers/{id}/logs?tail=100` restituisce le ultime N righe di log (stdout + stderr) del container. I container di sistema restituiscono 403.

`POST /services/create` crea un nuovo servizio da template. Il processo:
1. Copia la cartella `template_service` in `instances/{nome_servizio}`
2. Builda l'immagine Docker dalla cartella copiata
3. Avvia il container con i limiti di CPU e RAM specificati
4. La porta 8000 del container viene mappata su una porta casuale dell'host (per evitare conflitti)
5. Il build e l'avvio avvengono in un BackgroundTask di FastAPI, quindi la risposta arriva subito e il deploy continua in background

### 2. Servizio CV TrashNet (`cv_service_trashnet/`)

Servizio di classificazione rifiuti. Prende un'immagine in input e restituisce la categoria prevista (cardboard, glass, metal, paper, plastic, trash) con la confidence.

**Architettura a 3 livelli:**

`service/main.py` (livello API): definisce gli endpoint FastAPI. All'avvio chiama `engine.initialize()` tramite il pattern lifespan di FastAPI. Riceve le richieste HTTP e le inoltra all'engine.

`service/engine.py` (livello logica): fa da ponte. Gestisce lo stato del servizio (ready/not ready), misura la latenza delle inferenze, e gestisce i job di training in background. Tiene un dizionario `training_jobs` dove salva lo stato di ogni job con id, progresso e metriche.

`service/impl/algorithm.py` (livello modello): contiene il modello PyTorch vero e proprio.
- Usa MobileNetV2 pre-addestrato su ImageNet, con il layer classificatore finale sostituito per avere 6 output (le 6 classi di TrashNet)
- Le immagini vengono ridimensionate a 224x224 e normalizzate con media e deviazione standard di ImageNet
- Se trova dei pesi salvati in `data/model_weights.pth` li carica, altrimenti usa i pesi pre-addestrati di default
- L'inferenza avviene con `torch.no_grad()` per non sprecare memoria sui gradienti
- Il training usa solo il 10% del dataset (scaricato da HuggingFace) per tenerlo veloce in un contesto Docker/demo. Fa fine-tuning solo sul classifier head, non su tutta la rete. I pesi vengono salvati su disco alla fine.

**Contratto API standard (tutti i servizi CV devono implementare questi):**

| Endpoint | Metodo | Cosa fa | Input | Output |
|---|---|---|---|---|
| `/health` | GET | Verifica se il servizio e' pronto | nessuno | `{"status": "ok"}` |
| `/info` | GET | Restituisce nome, versione, classi | nessuno | JSON con capabilities |
| `/inference` | POST | Classifica un'immagine | immagine via form-data | `{"result": "glass", "confidence": 0.95, "latency_ms": 120}` |
| `/train` | POST | Avvia training in background | JSON con epochs, batch_size, lr | `{"job_id": "uuid", "status": "started"}` |
| `/train/{job_id}` | GET | Stato del training | nessuno | `{"status": "running", "progress": 45.0}` |

### 3. Template Service (`template_service/`)

Ha la stessa struttura del servizio TrashNet, ma l'algoritmo e' un placeholder. Quando l'utente crea un nuovo servizio dalla dashboard, il backend copia questa cartella, builda l'immagine Docker e avvia il container. Per implementare un nuovo algoritmo basta modificare `service/impl/algorithm.py` nella copia.

### 4. Frontend Web (`frontend_web/`)

Single Page Application scritta in React 18 con TypeScript. Compilata con Vite e servita da Nginx in produzione (Dockerfile multi-stage: Node per la build, Nginx per il serve).

**Librerie usate:**
- Tailwind CSS 4: stili utility-first, niente CSS custom tranne il reset base
- Framer Motion: animazioni delle card e dei modali
- Lucide React: icone (play, stop, trash, cpu, ecc)
- clsx + tailwind-merge: utility per combinare classi CSS condizionali

**Come funziona la dashboard:**
- Al mount, parte un `setInterval` che ogni 3 secondi chiama `GET /containers` e `GET /containers/{id}/stats` per ogni container running
- Le azioni (start, stop, delete) usano optimistic updates: aggiornano la UI immediatamente e poi confermano col server. Se il server risponde con errore, l'UI torna allo stato precedente
- La creazione di un nuovo servizio apre un modale con form per nome, CPU e RAM. Il submit chiama `POST /services/create`
- I log si vedono in un modale con sfondo scuro stile terminale
- Le notifiche toast appaiono in basso a destra e scompaiono dopo 5 secondi

### 5. Gradio UI (`gradio_ui/`)

Interfaccia opzionale per testare l'inferenza senza usare curl o Swagger. Usa il componente `gr.Image` di Gradio che supporta sia upload di file che webcam (l'icona per switchare appare automaticamente nell'interfaccia). L'URL del servizio CV target e' configurabile tramite variabile d'ambiente `SERVICE_URL`.

---

## Exploratory Data Analysis (EDA)

Il notebook `eda/eda.ipynb` analizza il dataset TrashNet (scaricato da HuggingFace `garythung/trashnet`):

1. **Distribuzione delle classi**: mostra quante immagini ci sono per ogni categoria. Il dataset e' sbilanciato (paper e glass hanno molte piu immagini di trash e cardboard). Questo e' un dato importante perche' un modello addestrato su dati sbilanciati potrebbe sviluppare bias verso le classi piu frequenti.

2. **Campioni visivi**: mostra un esempio di immagine per ogni classe, utile per capire la varianza visiva del dataset e le difficolta che il modello potrebbe incontrare.

Per eseguire il notebook in locale:
```bash
pip install datasets matplotlib numpy Pillow
jupyter notebook eda/eda.ipynb
```

---

## CI/CD con GitHub Actions

La pipeline e' definita in `.github/workflows/ci.yml` e si attiva ad ogni push su main/master.

**Job 1: test-and-lint**
1. Checkout del codice
2. Setup Python 3.10
3. Installazione di tutte le dipendenze (incluso PyTorch per i test del servizio CV)
4. Esecuzione test con pytest (genera report HTML e JUnit XML)
5. Linting con flake8 (controlla errori di sintassi bloccanti: E9, F63, F7, F82)
6. Validazione della configurazione docker-compose
7. Upload dei report di test e lint come artifact scaricabile dalla pagina Actions di GitHub

**Job 2: docker-build-and-push** (solo su push, non su pull request)
1. Login su Docker Hub (richiede i secrets `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN` configurati nel repo GitHub)
2. Build e push delle immagini: backend orchestrator, cv-service-trashnet, frontend-web

Per configurare i secrets su GitHub: Settings > Secrets and variables > Actions > New repository secret.

---

## Come eseguire i test in locale

```bash
# Dalla root del progetto
pip install pytest httpx fastapi uvicorn pydantic pyyaml docker python-multipart torch torchvision datasets Pillow

# Esegui tutti i test
PYTHONPATH=. pytest -v

# Esegui solo i test del backend
PYTHONPATH=. pytest backend_orchestrator/test_main.py -v

# Esegui solo i test del servizio CV
PYTHONPATH=. pytest cv_service_trashnet/test_cv_service.py -v
```

I test del backend verificano: health check, lista container (con o senza Docker), start/stop/delete su container inesistenti, stats, logs, creazione servizio con template mancante, validazione dei parametri.

I test del servizio CV verificano: health check, info con struttura corretta (6 classi, framework, ecc), inferenza con immagine dummy, avvio training, stato training inesistente, validazione parametri.

---

## Come eseguire il linting

```bash
# Linting Python con flake8
pip install flake8
flake8 template_service cv_service_trashnet backend_orchestrator gradio_ui --count --select=E9,F63,F7,F82 --show-source --statistics

# Linting frontend con ESLint
cd frontend_web
npm install
npm run lint
```

---

## Come funziona il Docker Compose

Il file `docker-compose.yml` definisce 4 servizi e 1 volume:

- **backend_orchestrator**: monta il socket Docker (`/var/run/docker.sock`) per poter gestire i container dall'interno. Monta anche la root del progetto come `/projects` per poter copiare il template quando crea nuovi servizi.

- **frontend_web**: serve i file statici React su porta 80 tramite Nginx. Dipende dal backend.

- **trashnet_service_default**: il servizio CV di esempio. Ha un volume persistente `trashnet_data` montato su `/app/data` per salvare i pesi del modello tra un restart e l'altro.

- **gradio_ui**: interfaccia opzionale. Il `SERVICE_URL` punta al servizio TrashNet tramite il nome del servizio nella rete Docker interna.

---

## Package Python

Il progetto e' anche installabile come pacchetto Python:
```bash
pip install -e .
```
Questo rende i moduli importabili (tipo `from backend_orchestrator.main import app`). I file `__init__.py` in ogni cartella servono a questo. Il `setup.py` nella root definisce nome, versione, autore e dipendenze principali.

---

## Tecnologie usate

| Componente | Tecnologie |
|---|---|
| Backend | Python 3.10, FastAPI, docker-py (Docker SDK), Pydantic, PyYAML |
| Servizio CV | PyTorch, TorchVision (MobileNetV2), HuggingFace Datasets, Pillow |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS 4, Framer Motion |
| Containerizzazione | Docker, Docker Compose, Nginx |
| CI/CD | GitHub Actions, Flake8, PyTest, Docker Hub |
| EDA | Jupyter Notebook, Matplotlib, NumPy |
| Interfaccia test | Gradio 5 |
