import time

class BaseAlgorithm:
    """
    Template base per un algoritmo di Computer Vision.
    Per creare un nuovo servizio, l'utente deve solo estendere questa classe.
    """
    def __init__(self, config):
        self.config = config
        self.model = None

    def load_model(self):
        """
        Carica i pesi del modello. 
        Qui andrebbe inserita la logica PyTorch/TensorFlow.
        """
        print("Caricamento modello mock dal template...")
        self.model = "MockModel_v1"

    def get_info(self):
        return {
            "algorithm": "BaseTemplateMock",
            "framework": "None"
        }

    def run_inference(self, image_bytes):
        """
        Esegue la simulazione dell'inferenza.
        Ritorna Result (stringa/dict) e Confidence (float).
        """
        # TODO: Implementare decodifica immagine reale
        print(f"Ricevuta immagine di {len(image_bytes)} bytes")
        
        # Simulazione inferenza
        time.sleep(0.5) 
        
        return "mock_prediction", 0.99

    def run_training(self, params, status_dict):
        """
        Simula il ciclo di vita del training
        """
        print(f"Training avviato con parametri: {params}")
        epochs = params.get("epochs", 1)
        
        for epoch in range(epochs):
            time.sleep(1) # Simula lavoro
            status_dict["progress"] = ((epoch + 1) / epochs) * 100
            print(f"Epoch {epoch+1}/{epochs} completata")
            
        print("Training concluso.")
        return {"loss": 0.05, "accuracy": 0.98}
