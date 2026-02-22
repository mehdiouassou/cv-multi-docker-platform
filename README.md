# Symphony: Piattaforma Multi-Docker per Computer Vision

Symphony è una piattaforma software distribuita sviluppata per gestire, orchestrare e monitorare algoritmi di Computer Vision in forma di microservizi containerizzati (Docker). Il progetto rispetta rigidamente un approccio architetturale basato su API REST standardizzate e comunicazione asincrona.

L'infrastruttura è stata concepita per soddisfare i requisiti di automazione e scalabilità, integrando:
- Un backend orchestratore potente e sicuro.
- Una dashboard frontend intuitiva e dinamica.
- Un sistema per lo scaffolding (creazione da template) di nuovi servizi di Computer Vision.
- Persistenza dei dati di addestramento e un'infrastruttura di Continuous Integration / Continuous Deployment (CI/CD).

A fini dimostrativi, la piattaforma include un classificatore PyTorch (`cv_service_trashnet`) addestrato in origine su un subset del dataset `garythung/trashnet` per la separazione in classi dei rifiuti (cartone, vetro, metallo, carta, plastica).

---

## 📸 Architettura del Sistema

L'intero sistema ruota attorno a cinque pilastri fondamentali (microservizi creati nativamente o gestiti dinamicamente):

1. **`backend_orchestrator` (Core):**
   - API sviluppata in Python tramite FastAPI.
   - Utilizza l'SDK ufficiale `docker-py` per interagire con il Docker Daemon host attraverso un volume condiviso (`/var/run/docker.sock`).
   - Gestisce i deployment dinamici (creazione servizi da template), avvio/arresto dei container e la limitazione delle risorse (RAM e CPU limitate tramite parametri dell'API).
   - Impedisce l'eliminazione incidentale dei servizi core per garantire stabilità.

2. **`frontend_web` (Dashboard UI):**
   - Single Page Application asincrona sviluppata in puro React 18, arricchita da Tailwind CSS per una grafica moderna e un layout reattivo.
   - Comunica costantemente in polling veloce con il backend per visualizzare le statistiche di rete/CPU, lo stato vitale (running/stopped) e i log di sistema in tempo reale dei vari container senza forzare reload della pagina.

3. **`cv_service_trashnet` (Servizio CV di Base):**
   - Basato sul modello deep learning MobileNet-V2. 
   - Espone gli endpoint standard imposti dal contratto API della piattaforma (vedi sezione API sottostante).
   - Supporta un processo di fine-tuning asincrono con persistenza garantita dei pesi grazie ai volumi definiti a livello di orchestrazione (Docker Compose).

4. **`template_service` (Blueprint di creazione):**
   - Progetto base di riferimento che l'orchestratore "clona" quando riceve la richiesta di generare un nuovo container indipendente da interfaccia web. Contiene le dipendenze essenziali ed un algoritmo base da sovrascrivere.

5. **`gradio_ui` (Testing Visivo):**
   - Microscopica interfaccia accessoria per collaudo rapido. Manda una richiesta in `multipart/form-data` all'endpoint di inferenza del container CV puntato.

---

## 🛠 Prerequisiti

Per eseguire questo progetto, assicurati di possedere:

- **Docker Engine** (testato su v24.0.5+ o Docker Desktop su Windows/Mac)
- **Docker Compose**
- *(Opzionale)* `Python 3.10+` se desideri ispezionare manualmente la directory EDA, i Makefile o lanciare test unitari al di fuori del nodo dockerizzato.

---

## 🚀 Guida all'Avvio (Deployment Rapido)

L'intera logistica di build e deploy è orchestrata con uno script dichiarativo. Dal terminale di comando, digita:

```bash
# 1. Clona il repository Git in locale
git clone https://github.com/[INSERISCI_URL_REPO]/cv-multi-docker-platform.git
cd cv-multi-docker-platform

# 2. Compila i microservizi core (il processo impiegherà qualche istante per scaricare i layer Python/Node base)
docker compose build

# 3. Avvia lo stack intero disconnettendo l'output (modalità detach)
docker compose up -d
```

### Accesso ai Componenti
Una volta stabilito il sistema, avrai accesso locale tramite browser:

- **Frontend Dashboard:** [http://localhost](http://localhost) *(Porta 80 mapeggiata nativamente)*
- **Hub Orchestratore (Swagger API):** [http://localhost:8080/docs](http://localhost:8080/docs)
- **Servizio CV TrashNet (Swagger API):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Interfaccia Upload Immagini Gradio:** [http://localhost:7860](http://localhost:7860)

---

## 📡 Contratto API Standard per i Servizi CV

Ogni microservizio per il calcolo ed inferenza visiva che viene fatto orbitare attorno a Symphony implementa obbligatoriamente il seguente stack API:

- `GET /health` : Restituisce un JSON snello `{ "status": "ok" }`. L'orchestratore usa questa via per sondare la readiness.
- `GET /info` : Espone metadati operativi e layer architetturali usati.
- `POST /inference` : Accetta un body di tipo form-data. Restituisce il dict con format: `{"result": "class", "confidence": 0.99, "latency_ms": 120.5}`.
- `POST /train` : Riceve l'input di iper-parametri (`epochs`, `batch_size`). Esegue una computazione intensiva scorporando il flusso HTTP tramite un job manager (FastAPI BackgroundTasks), ritornando senza latenza un identificatore di processo `{"job_id": "xxxxx"}`.
- `GET /train/{job_id}`: Contiene diagnostica sull'addestramento in background (percentuale di avanzamento e/o eventuale stato fallimentare).

---

## 📊 Pipeline CI/CD, Package Python & Analisi Dati (EDA)

Questo progetto si spinge oltre la mera scrittura di codice, dimostrando un'architettura enterprise sostenibile e documentata:

### 1. Pacchetto Python (Installazione Modulare)
Il repository espone il file `setup.py` all'interno della sua cartella `root`. È possibile installare tutto il software, ed ogni servizio, operando in modalità sorgente:
```bash
pip install -e .
```
L'aggiunta strategica dei package namespaces tramite i fle `__init__.py` certifica che la codebase sia compatibile a livello di importazione come pacchetto puro.

### 2. Jupyter Notebook ed EDA
Situata nella directory `eda/`, è presente una minuziosa *Exploratory Data Analysis* del dataset *TrashNet*. Nel documento Python/Notebook sono analizzati il bilanciamento delle etichette del dataset (che giustifica possibili bias in un task multishot e i pesi delle cross-entropy loss) e gli output visivi delle categorie.

### 3. GitHub Actions
La cartella `.github/workflows/ci.yml` è configurata nativamente per compiere i seguenti step al `push` sul branch `main/master`:
1.  Setup ambiente Python pulito virtuale.
2.  Chiamata a `pip` per le dipendenze, controlli stringenti di `flake8` (linting).
3.  Unit Testing con **PyTest** validando asincronicità delle route di FastAPI nell'Orchestratore e nel template.
4.  Build di `docker-compose.yml` e pubblicazione immagine pubblica su Docker Hub. Requisiti necessari: `secrets.DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN`.

---
*Progetto curato con cura per un'istruzione architetturale scalabile e moderna.*
