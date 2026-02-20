# Symphony: Piattaforma Multi-Docker CV

Symphony è una piattaforma progettata per orchestrare, gestire e monitorare algoritmi di Computer Vision eseguiti all'interno di container Docker isolati. L'architettura comprende un backend di orchestrazione, una dashboard web per il monitoraggio in tempo reale, pipeline di CI/CD automatizzate e un'interfaccia interattiva per l'inferenza.

L'implementazione principale fornita in questo repository è il **Classificatore TrashNet**, un modello PyTorch personalizzato per la classificazione dei rifiuti.

## Panoramica dell'Architettura

Il sistema è composto da cinque microservizi debolmente accoppiati (loosely coupled):

1. **backend_orchestrator**: API REST sviluppata con FastAPI. Utilizza il Docker SDK per Python per interagire nativamente con il demone Docker host, gestendo il ciclo di vita dei container e applicando vincoli di CPU e memoria.
2. **frontend_web**: Single Page Application (SPA) leggera realizzata in Vanilla JavaScript e Tailwind CSS. Si interfaccia con l'orchestratore per la telemetria in tempo reale e il provisioning dei servizi.
3. **template_service**: Template standard che definisce il contratto API richiesto (`/health`, `/info`, `/inference`, `/train`) per qualsiasi nuovo servizio di Computer Vision integrato nella piattaforma.
4. **cv_service_trashnet**: Implementazione concreta del template. Espone un modello PyTorch MobileNetV2 sottoposto a fine-tuning sul dataset `garythung/trashnet` di Hugging Face.
5. **gradio_ui**: Applicazione Gradio containerizzata e indipendente, sviluppata per test visivi di inferenza in tempo reale sul servizio CV attivo.

Una directory aggiuntiva `eda` contiene i Jupyter Notebook utilizzati per l'Analisi Esplorativa dei Dati (Exploratory Data Analysis) prima dell'addestramento del modello.

## Deployment Locale

L'intero stack è orchestrato tramite Docker Compose. Assicurarsi che Docker Desktop o il demone Docker siano in esecuzione sulla macchina host.

### Prerequisiti
- Docker Engine 20.10+
- Docker Compose v2+

### Avvio Rapido

1. Clonare il repository:
   ```bash
   git clone https://github.com/[TUO_USERNAME]/cv-multi-docker-platform.git
   cd cv-multi-docker-platform
   ```

2. Compilare e avviare l'infrastruttura:
   ```bash
   docker-compose up --build -d
   ```

### Punti di Accesso

Una volta avviati i servizi, sono disponibili le seguenti interfacce:

- **Dashboard Web**: http://localhost:80
- **UI di Inferenza Gradio**: http://localhost:7860
- **Documentazione API Orchestratore**: http://localhost:8080/docs
- **Documentazione API Servizio TrashNet**: http://localhost:8000/docs

## Dettagli di Implementazione Tecnica

- **Elaborazione Asincrona**: L'architettura backend fa ampio uso di operazioni asincrone (`BackgroundTasks` in FastAPI) per prevenire il blocco delle richieste HTTP durante task intensivi come l'addestramento dei modelli o la compilazione dei container.
- **Design del Modello**: Il servizio di Computer Vision (`cv_service_trashnet/service/impl/algorithm.py`) segue un approccio orientato agli oggetti, estendendo una classe base astratta definita nel template.
- **Contratto API**: L'implementazione rispetta rigorosamente le specifiche richieste:
  - `GET /health` e `GET /info` per controlli di vitalità e funzionalità.
  - `POST /inference` per le predizioni standard sincrone.
  - `POST /train` per l'avvio asincrono dell'addestramento in background.
- **CI/CD**: I workflow di GitHub Actions, configurati in `.github/workflows`, eseguono linting automatico (Flake8), validazione della configurazione e pubblicazione delle immagini su Docker Hub in seguito agli eventi di push.
