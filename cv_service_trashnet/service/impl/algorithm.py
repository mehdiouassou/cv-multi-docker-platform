"""
BaseAlgorithm - Implementazione del modello di classificazione rifiuti.

Usa MobileNetV2 (pre-addestrato su ImageNet) con il layer classificatore
finale sostituito per 6 classi: cardboard, glass, metal, paper, plastic, trash.

Il modello puo essere usato sia per inferenza che per fine-tuning:
- Inferenza: prende un'immagine, la preprocessa e restituisce classe e confidence
- Training: scarica un subset del dataset TrashNet da HuggingFace e fa fine-tuning
  solo sul classifier head (non sull'intera rete, per velocita)
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import models, transforms
from torchvision.models import MobileNet_V2_Weights
from PIL import Image
import io
import time
import os

from datasets import load_dataset
from torch.utils.data import DataLoader, Dataset


class BaseAlgorithm:
    def __init__(self, config):
        self.config = config
        # Usa GPU se disponibile, altrimenti CPU
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.classes = ['cardboard', 'glass', 'metal', 'paper', 'plastic', 'trash']
        self.num_classes = len(self.classes)
        self.model = None

        # Pipeline di trasformazione delle immagini:
        # 1. Ridimensiona a 224x224 (dimensione attesa da MobileNetV2)
        # 2. Converte in tensore PyTorch (valori 0-1)
        # 3. Normalizza con media e std di ImageNet (necessario perche' il modello
        #    e' pre-addestrato su ImageNet con questi parametri)
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def load_model(self):
        """
        Inizializza MobileNetV2 e sostituisce il classifier finale.

        MobileNetV2 di default ha 1000 classi (ImageNet). Noi sostituiamo
        l'ultimo layer lineare con uno da 6 output per le nostre classi.

        Se esistono pesi salvati da un training precedente (in data/model_weights.pth),
        li carica. Altrimenti usa i pesi pre-addestrati di ImageNet come base.
        """
        print("Inizializzazione MobileNetV2 per TrashNet...")
        self.model = models.mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)

        # Sostituiamo solo l'ultimo layer: da 1000 classi ImageNet a 6 classi TrashNet
        self.model.classifier[1] = nn.Linear(self.model.last_channel, self.num_classes)

        # Carica pesi custom se disponibili (salvati da un training precedente)
        pesi_path = "data/model_weights.pth"
        if os.path.exists(pesi_path):
            try:
                self.model.load_state_dict(torch.load(pesi_path, map_location=self.device, weights_only=True))
                print(f"Pesi custom caricati da {pesi_path}")
            except Exception as e:
                print(f"Errore nel caricare i pesi custom: {e}")

        self.model = self.model.to(self.device)
        self.model.eval()  # Modalita' valutazione (disabilita dropout e batch norm training)

    def get_info(self):
        """Restituisce le informazioni sull'algoritmo usato."""
        return {
            "algorithm": "MobileNetV2_TrashNet",
            "framework": "PyTorch",
            "classes": self.classes,
            "device": str(self.device)
        }

    def run_inference(self, image_bytes):
        """
        Classifica un'immagine partendo dai bytes raw.

        Processo:
        1. Apre l'immagine dai bytes e la converte in RGB
        2. Applica le trasformazioni (resize, normalize)
        3. Aggiunge la dimensione batch (unsqueeze) perche' il modello si aspetta [B, C, H, W]
        4. Passa il tensore al modello con torch.no_grad() per non calcolare i gradienti
        5. Applica softmax per ottenere le probabilita per ogni classe
        6. Prende la classe con probabilita massima

        Restituisce (nome_classe, confidence).
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tensor = self.transform(image).unsqueeze(0).to(self.device)

            # no_grad disabilita il calcolo dei gradienti: risparmia memoria e velocizza
            with torch.no_grad():
                outputs = self.model(tensor)
                probabilities = torch.nn.functional.softmax(outputs[0], dim=0)

            confidence, predicted_idx = torch.max(probabilities, 0)
            prediction = self.classes[predicted_idx.item()]
            conf_val = round(confidence.item(), 4)

            return prediction, conf_val
        except Exception as e:
            print(f"Errore inferenza: {e}")
            return "error", 0.0

    def run_training(self, params, status_dict):
        """
        Esegue il fine-tuning del modello sul dataset TrashNet.

        Parametri accettati:
        - epochs: numero di passaggi completi sul dataset
        - learning_rate: tasso di apprendimento per Adam
        - batch_size: immagini per batch

        Usa solo il 10% del dataset per tenere il training veloce in un contesto
        Docker demo (altrimenti su CPU ci vorrebbero ore).

        L'optimizer aggiorna solo i parametri del classifier head
        (self.model.classifier), non dell'intera rete. Questo e' il classico
        approccio di transfer learning: il backbone resta congelato e si
        allena solo la testa di classificazione.

        Il progresso viene aggiornato in tempo reale nel status_dict passato
        per reference dall'engine, cosi l'endpoint GET /train/{job_id} puo
        mostrare la percentuale di completamento.
        """
        print(f"Avvio processo di training (PyTorch) - Params: {params}")
        epochs = params.get("epochs", 1)
        lr = params.get("learning_rate", 0.001)
        batch_size = params.get("batch_size", 16)

        # Scarica un subset del dataset da HuggingFace (10% per velocita)
        try:
            print("Caricamento dataset TrashNet (subset train 10%)...")
            dataset = load_dataset("garythung/trashnet", split="train[:10%]")
        except Exception as e:
            return {"error": f"Errore caricamento dataset: {str(e)}"}

        # Wrapper PyTorch per il dataset HuggingFace: applica le trasformazioni
        # e restituisce (tensore_immagine, label) come si aspetta il DataLoader
        class TrashNetHF(Dataset):
            def __init__(self, hf_dataset, transform):
                self.hf_dataset = hf_dataset
                self.transform = transform
            def __len__(self): return len(self.hf_dataset)
            def __getitem__(self, idx):
                item = self.hf_dataset[idx]
                img = item['image'].convert("RGB")
                label = item['label']
                return self.transform(img), label

        train_data = TrashNetHF(dataset, self.transform)
        loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)

        # Mettiamo il modello in modalita training (attiva dropout e batch norm)
        self.model.train()

        # Adam solo sui parametri del classifier (transfer learning)
        optimizer = optim.Adam(self.model.classifier.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        total_steps = epochs * len(loader)
        current_step = 0

        for epoch in range(epochs):
            running_loss = 0.0
            for i, (inputs, labels) in enumerate(loader):
                inputs, labels = inputs.to(self.device), labels.to(self.device)

                # Forward pass, calcolo loss, backward pass, aggiornamento pesi
                optimizer.zero_grad()
                outputs = self.model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                running_loss += loss.item()
                current_step += 1

                # Aggiorna il progresso ogni 5 step (visibile da GET /train/{job_id})
                if current_step % 5 == 0 or current_step == total_steps:
                    progress = round((current_step / total_steps) * 100, 2)
                    status_dict["progress"] = progress
                    print(f"Epoch {epoch+1}/{epochs} - Batch {i}/{len(loader)} - Loss: {loss.item():.4f}")

        # Salva i pesi su disco (il volume Docker li mantiene tra i restart)
        os.makedirs("data", exist_ok=True)
        torch.save(self.model.state_dict(), "data/model_weights.pth")
        print("Training concluso. Pesi salvati in data/model_weights.pth")

        # Torna in modalita valutazione per le prossime inferenze
        self.model.eval()
        avg_loss = running_loss / len(loader) if len(loader) > 0 else 0
        return {"loss": round(avg_loss, 4), "epochs_completed": epochs}
