"""
Template base per un algoritmo di Computer Vision.

Questo file e' un placeholder. Quando un nuovo servizio viene creato dalla
dashboard, il backend copia tutta la cartella template_service e il nuovo
servizio parte con questo algoritmo mock.

Per implementare un algoritmo reale bisogna:
1. Modificare load_model() per caricare il modello vero (PyTorch, TensorFlow, ecc)
2. Modificare run_inference() per preprocessare l'immagine e restituire la predizione
3. Modificare run_training() per implementare il training loop reale
4. Aggiornare get_info() con le informazioni corrette
5. Aggiornare requirements.txt con le dipendenze necessarie (torch, ecc)
"""

import time


class BaseAlgorithm:
    def __init__(self, config):
        self.config = config
        self.model = None

    def load_model(self):
        """
        Qui va caricato il modello vero.
        Esempio con PyTorch:
            self.model = models.mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
            self.model.eval()
        """
        print("Caricamento modello mock dal template...")
        self.model = "MockModel_v1"

    def get_info(self):
        """Restituisce informazioni sull'algoritmo. Da aggiornare col modello reale."""
        return {
            "algorithm": "BaseTemplateMock",
            "framework": "None"
        }

    def run_inference(self, image_bytes):
        """
        Qui va implementata l'inferenza reale.
        Riceve i bytes dell'immagine e deve restituire (predizione, confidence).

        Esempio:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tensor = self.transform(image).unsqueeze(0)
            with torch.no_grad():
                output = self.model(tensor)
            return classe_predetta, confidence
        """
        print(f"Ricevuta immagine di {len(image_bytes)} bytes")

        # Simulazione inferenza (sostituire con codice reale)
        time.sleep(0.5)
        return "mock_prediction", 0.99

    def run_training(self, params, status_dict):
        """
        Qui va implementato il training loop reale.
        status_dict viene passato per reference: aggiornare status_dict["progress"]
        permette di mostrare il progresso dall'endpoint GET /train/{job_id}.
        """
        print(f"Training avviato con parametri: {params}")
        epochs = params.get("epochs", 1)

        for epoch in range(epochs):
            time.sleep(1)  # Simulazione lavoro
            status_dict["progress"] = ((epoch + 1) / epochs) * 100
            print(f"Epoch {epoch+1}/{epochs} completata")

        print("Training concluso.")
        return {"loss": 0.05, "accuracy": 0.98}
