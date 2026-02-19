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
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.classes = ['cardboard', 'glass', 'metal', 'paper', 'plastic', 'trash']
        self.num_classes = len(self.classes)
        self.model = None
        
        # Trasformazioni base per inferenza e training su ImageNet/MobileNet
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def load_model(self):
        print("Inizializzazione MobileNetV2 per TrashNet...")
        self.model = models.mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
        # Sostituiamo il decision layer per le 6 classi
        self.model.classifier[1] = nn.Linear(self.model.last_channel, self.num_classes)
        
        pesi_path = "data/model_weights.pth"
        if os.path.exists(pesi_path):
            try:
                self.model.load_state_dict(torch.load(pesi_path, map_location=self.device))
                print(f"Pesi custom caricati da {pesi_path}")
            except Exception as e:
                print(f"Errore nel caricare i pesi custom: {e}")
                
        self.model = self.model.to(self.device)
        self.model.eval()

    def get_info(self):
        return {
            "algorithm": "MobileNetV2_TrashNet",
            "framework": "PyTorch",
            "classes": self.classes,
            "device": str(self.device)
        }

    def run_inference(self, image_bytes):
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tensor = self.transform(image).unsqueeze(0).to(self.device)
            
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
        print(f"Avvio processo di training (PyTorch) - Params: {params}")
        epochs = params.get("epochs", 1)
        lr = params.get("learning_rate", 0.001)
        batch_size = params.get("batch_size", 16)
        
        # Usiamo un subset leggero (10%) per garantire esecuzione rapida su CPU (es. Docker demo)
        try:
            print("Caricamento dataset TrashNet (subset train 10%)...")
            dataset = load_dataset("garythung/trashnet", split="train[:10%]")
        except Exception as e:
            return {"error": f"Errore caricamento dataset: {str(e)}"}

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
        
        self.model.train()
        optimizer = optim.Adam(self.model.classifier.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()
        
        total_steps = epochs * len(loader)
        current_step = 0
        
        for epoch in range(epochs):
            running_loss = 0.0
            for i, (inputs, labels) in enumerate(loader):
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                
                running_loss += loss.item()
                current_step += 1
                
                if current_step % 5 == 0 or current_step == total_steps:
                    progress = round((current_step / total_steps) * 100, 2)
                    status_dict["progress"] = progress
                    print(f"Epoch {epoch+1}/{epochs} - Batch {i}/{len(loader)} - Loss: {loss.item():.4f}")

        os.makedirs("data", exist_ok=True)
        torch.save(self.model.state_dict(), "data/model_weights.pth")
        print("Training concluso. Pesi salvati in data/model_weights.pth")
        
        self.model.eval()
        avg_loss = running_loss / len(loader) if len(loader) > 0 else 0
        return {"loss": round(avg_loss, 4), "epochs_completed": epochs}
