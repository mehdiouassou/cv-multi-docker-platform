import uuid
import time
from service.impl.algorithm import BaseAlgorithm

class CVEngine:
    """
    Motore principale per gestire le chiamate algoritmo e mantenere lo stato del servizio.
    Isola il layer FastAPI dall'effettiva implementazione del modello di Computer Vision.
    """
    def __init__(self, config):
        self.config = config
        self.algorithm = BaseAlgorithm(config)
        self.ready = False
        self.training_jobs = {} # Tiene traccia dello stato dei job di training

    def initialize(self):
        """Prepara il modello base"""
        self.algorithm.load_model()
        self.ready = True

    def is_ready(self):
        return self.ready

    def get_capabilities(self):
        return self.algorithm.get_info()

    def predict(self, image_bytes):
        """Pre-processa l'immagine, chiama l'algoritmo e formatta l'output"""
        if not self.ready:
            raise Exception("Engine non inizializzato")
        
        start_time = time.time()
        
        # Inoltra all'algoritmo specifico
        prediction, confidence = self.algorithm.run_inference(image_bytes)
        
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        return {
            "result": prediction,
            "confidence": confidence,
            "latency_ms": latency_ms
        }

    def start_training(self, params, background_tasks):
        """Accoda un task asincrono di training e ritorna il job ID"""
        job_id = str(uuid.uuid4())
        self.training_jobs[job_id] = {
            "status": "running",
            "progress": 0.0,
            "metrics": {}
        }
        
        # Aggiunge il processo alla coda in background offerta da FastAPI
        background_tasks.add_task(self._training_task, job_id, params)
        return job_id

    def _training_task(self, job_id, params):
        """Metodo che verrà eseguito in background. Delega all'algoritmo."""
        try:
            # L'algoritmo può aggiornare lo stato chiamando delle callback o noi lo passiamo per reference
            result = self.algorithm.run_training(params, self.training_jobs[job_id])
            self.training_jobs[job_id]["status"] = "completed"
            self.training_jobs[job_id]["metrics"] = result
            
            # Ricostruisce il motore per caricare il nuovo modello
            self.initialize()
        except Exception as e:
            self.training_jobs[job_id]["status"] = "failed"
            self.training_jobs[job_id]["error"] = str(e)

    def get_training_status(self, job_id):
        return self.training_jobs.get(job_id)
