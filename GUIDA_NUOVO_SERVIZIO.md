# Guida: Creare un nuovo servizio CV (esempio Face Detector)

Questa guida spiega come creare un nuovo servizio di Computer Vision partendo dal template della piattaforma. Come esempio creeremo un servizio di **rilevamento volti** usando OpenCV.

## Prerequisiti

- Docker Desktop avviato
- Piattaforma Symphony in esecuzione (`docker compose up -d`)

## Step 1 - Creare il template dalla dashboard

Aprire `http://localhost` nel browser e cliccare **"Nuovo Servizio"**.

Compilare i campi:
- **Nome servizio**: `face_detector`
- **CPU cores**: `1.0`
- **Memoria (MB)**: `512`

Cliccare **"Crea Template"**. La piattaforma copiera' il template in `instances/face_detector/` e il servizio apparira' nella sezione **"Servizi in Attesa di Setup"** con stato **da configurare**.

> La porta viene assegnata automaticamente da Docker al momento del deploy, quindi non ci sono conflitti.

## Step 2 - Struttura dei file generati

Il template genera questa struttura:

```
instances/face_detector/
├── Dockerfile              <- build del container (non serve modificarlo)
├── config.yaml             <- nome e descrizione del servizio
├── requirements.txt        <- dipendenze Python
└── service/
    ├── main.py             <- API FastAPI (non serve modificarlo)
    ├── engine.py           <- bridge tra API e algoritmo (non serve modificarlo)
    └── impl/
        └── algorithm.py    <- QUESTO E' IL FILE DA MODIFICARE
```

I file `main.py` e `engine.py` gestiscono automaticamente gli endpoint (`/health`, `/info`, `/inference`, `/train`) e la misurazione della latenza. L'unico file da toccare per implementare un algoritmo custom e' **`algorithm.py`**.

La dashboard mostra i path esatti dei 3 file da modificare nella card del servizio in attesa.

## Step 3 - Modificare `config.yaml`

Aprire `instances/face_detector/config.yaml` e aggiornare nome e descrizione:

```yaml
service:
  name: "FaceDetector"
  version: "1.0.0"
  description: "Servizio di rilevamento volti basato su OpenCV Haar Cascades"
model:
  task: "detection"
  input_size: [640, 480]
```

## Step 4 - Aggiungere le dipendenze in `requirements.txt`

Aprire `instances/face_detector/requirements.txt` e aggiungere le librerie necessarie per l'algoritmo. Per il face detector servono OpenCV e NumPy:

```
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.4
python-multipart==0.0.9
PyYAML==6.0.1
opencv-python-headless==4.9.0.80
numpy==1.26.4
```

> Nota: le prime 5 righe sono quelle del template e non vanno rimosse. Aggiungere le proprie dipendenze in fondo.

## Step 5 - Implementare l'algoritmo in `algorithm.py`

Questo e' il passo principale. Aprire `instances/face_detector/service/impl/algorithm.py` e sostituire il contenuto con il proprio algoritmo.

La classe deve chiamarsi **`BaseAlgorithm`** e implementare questi 4 metodi:

| Metodo | Cosa fa |
|--------|---------|
| `load_model()` | Carica il modello in memoria (chiamato una volta all'avvio) |
| `get_info()` | Restituisce nome algoritmo, framework e classi supportate |
| `run_inference(image_bytes)` | Riceve i bytes dell'immagine, restituisce `(predizione, confidence)` |
| `run_training(params, status_dict)` | Implementa il training (opzionale, puo' restituire subito) |

Esempio completo per il face detector:

```python
import cv2
import numpy as np


class BaseAlgorithm:
    def __init__(self, config):
        self.config = config
        self.model = None

    def load_model(self):
        """Carica il classificatore Haar Cascade per il face detection."""
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.model = cv2.CascadeClassifier(cascade_path)

    def get_info(self):
        return {
            "algorithm": "HaarCascade_FaceDetector",
            "framework": "OpenCV",
            "classes": ["face"]
        }

    def run_inference(self, image_bytes):
        """Riceve i bytes dell'immagine e rileva i volti."""
        # Decodifica immagine da bytes a numpy array
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is None:
            return "errore_decodifica", 0.0

        # Converti in scala di grigi (richiesto da Haar Cascade)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Rileva i volti
        faces = self.model.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        num_faces = len(faces)
        if num_faces == 0:
            return "nessun_volto", 0.0

        confidence = min(1.0, num_faces * 0.3 + 0.5)
        return f"{num_faces}_volti_rilevati", round(confidence, 2)

    def run_training(self, params, status_dict):
        """Haar Cascade non richiede training."""
        status_dict["progress"] = 100
        return {"note": "Algoritmo pre-addestrato, training non necessario."}
```

## Step 6 - Build & Deploy dalla dashboard

Una volta modificati i file, tornare sulla dashboard (`http://localhost`). Nella sezione **"Servizi in Attesa di Setup"** cliccare il bottone **"Build & Deploy"** sulla card del servizio.

La piattaforma:
1. Builda l'immagine Docker dalla cartella del servizio
2. Avvia il container con i limiti di CPU e RAM impostati
3. Assegna automaticamente una porta libera

Durante il build la card mostra uno spinner "Build in corso...". Se il build fallisce (ad esempio per un errore in `requirements.txt` o nel codice), l'errore viene mostrato direttamente nella card con un bottone **"Riprova Build"** per ritentare dopo aver corretto il problema.

Quando il build e' completato, il servizio scompare dalla sezione "In Attesa" e appare nella sezione **"Servizi Deployed"** con stato **running**.

## Step 7 - Testare il servizio

Il servizio e' testabile direttamente dalla dashboard: nella card del servizio appare la sezione **"Test Inferenza"** dove si puo' caricare un'immagine e vedere il risultato.

In alternativa, dalla dashboard si puo' vedere la porta assegnata al servizio e testare via terminale:

```bash
# La porta viene mostrata nella card del servizio (es. localhost:52571)
# Health check
curl http://localhost:<porta>/health
# Risposta: {"status":"ok"}

# Info servizio
curl http://localhost:<porta>/info
# Risposta: {"name":"FaceDetector","version":"1.0.0",...}

# Inferenza
curl -X POST http://localhost:<porta>/inference -F "file=@foto.jpg"
# Risposta: {"result":"1_volti_rilevati","confidence":0.8,"latency_ms":450.0}
```

## Riepilogo

Per creare un servizio CV custom:

1. **Dashboard**: clicca "Nuovo Servizio" e compila nome + risorse
2. **Editor**: modifica i 3 file (`config.yaml`, `requirements.txt`, `algorithm.py`)
3. **Dashboard**: clicca "Build & Deploy"

Tutto il resto (endpoint API, health check, misura latenza, gestione training jobs, assegnazione porta) e' gestito automaticamente dalla piattaforma.
