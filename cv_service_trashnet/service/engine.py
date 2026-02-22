"""
CVEngine - Livello intermedio tra le API FastAPI e l'algoritmo di Computer Vision.

Questo modulo fa da ponte: riceve le richieste dall'API (main.py), le inoltra
all'algoritmo concreto (algorithm.py) e gestisce lo stato del servizio.

Responsabilita:
- Inizializzazione del modello al boot del container
- Misura della latenza di ogni inferenza
- Gestione dei job di training in background (creazione, tracking, completamento)
"""

import uuid
import time
from service.impl.algorithm import BaseAlgorithm


class CVEngine:
    def __init__(self, config):
        self.config = config
        self.algorithm = BaseAlgorithm(config)
        self.ready = False
        # Dizionario che tiene traccia di tutti i job di training lanciati.
        # Chiave: job_id (UUID), Valore: dict con status, progress, metrics
        self.training_jobs = {}

    def initialize(self):
        """Carica il modello in memoria. Chiamato una volta sola all'avvio del container."""
        self.algorithm.load_model()
        self.ready = True

    def is_ready(self):
        """Usato dall'endpoint /health per verificare se il modello e' caricato."""
        return self.ready

    def get_capabilities(self):
        """Restituisce le info sull'algoritmo (nome, framework, classi supportate)."""
        return self.algorithm.get_info()

    def predict(self, image_bytes):
        """
        Esegue l'inferenza su un'immagine.

        Riceve i bytes dell'immagine, li passa all'algoritmo e restituisce
        il risultato formattato con predizione, confidence e latenza in ms.
        """
        if not self.ready:
            raise Exception("Engine non inizializzato")

        start_time = time.time()
        prediction, confidence = self.algorithm.run_inference(image_bytes)
        latency_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "result": prediction,
            "confidence": confidence,
            "latency_ms": latency_ms
        }

    def start_training(self, params, background_tasks):
        """
        Avvia un job di training in background.

        Genera un UUID come job_id, inizializza lo stato del job e lo accoda
        come BackgroundTask di FastAPI. Restituisce il job_id al chiamante
        che puo usarlo per controllare lo stato con get_training_status().
        """
        job_id = str(uuid.uuid4())
        self.training_jobs[job_id] = {
            "status": "running",
            "progress": 0.0,
            "metrics": {}
        }

        background_tasks.add_task(self._training_task, job_id, params)
        return job_id

    def _training_task(self, job_id, params):
        """
        Eseguito in background da FastAPI. Delega il training all'algoritmo
        passandogli il dizionario di stato per reference, cosi l'algoritmo
        puo aggiornare il progresso in tempo reale.

        Al completamento, ricarica il modello per usare i pesi appena salvati.
        """
        try:
            result = self.algorithm.run_training(params, self.training_jobs[job_id])
            self.training_jobs[job_id]["status"] = "completed"
            self.training_jobs[job_id]["metrics"] = result

            # Dopo il training ricarica il modello per usare i nuovi pesi
            self.initialize()
        except Exception as e:
            self.training_jobs[job_id]["status"] = "failed"
            self.training_jobs[job_id]["error"] = str(e)

    def get_training_status(self, job_id):
        """Restituisce lo stato di un job di training, o None se non esiste."""
        return self.training_jobs.get(job_id)
