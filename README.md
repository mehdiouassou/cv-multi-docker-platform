# Piattaforma Multi-Docker per Computer Vision

Questo progetto implementa una piattaforma per la gestione, l'orchestrazione e il monitoraggio di container Docker dedicati all'esecuzione di algoritmi di Computer Vision. Il sistema è dotato di un'interfaccia grafica web e permette la generazione automatica di nuovi servizi tramite un template predefinito.

## Funzionalità Principali

1. **Gestione Container:** Avvio, arresto e monitoraggio di più container Docker.
2. **API Standardizzata:** Interrogazione di ogni container tramite un contratto API standard (health, info, inference, train).
3. **Template:** Creazione di nuovi servizi a partire da un template standardizzato.
4. **Gestione Risorse:** Configurazione personalizzata dei limiti di CPU e memoria per ogni container.
5. **Web UI:** Gestione completa del sistema tramite dashboard HTML/JS.

## Struttura del Progetto

- `backend_orchestrator/`: API per la gestione dell'orchestrazione dei container Docker.
- `frontend_web/`: Interfaccia grafica.
- `template_service/`: Template base per nuovi servizi Computer Vision.
- `cv_service_trashnet/`: Esempio di servizio CV implementato (Classificazione Rifiuti).
- `gradio_ui/`: Interfaccia utente interattiva basata su Gradio.
- `eda/`: Jupyter Notebook per l'Analisi Esplorativa dei Dati (Exploratory Data Analysis).

## Installazione e Avvio Rapido

(Le istruzioni dettagliate verranno popolate in fase di deployment del docker-compose).
