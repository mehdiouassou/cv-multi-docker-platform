import pytest
from fastapi.testclient import TestClient
import sys
import os
import io

current_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(current_dir))

from service.main import app, engine

# Usiamo il context manager per attivare il lifespan (carica il modello)
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def init_engine():
    """Inizializza l'engine una volta sola per tutti i test del modulo."""
    if not engine.is_ready():
        engine.initialize()


def test_cv_health():
    response = client.get("/health")
    assert response.status_code in [200, 503]


def test_cv_info():
    response = client.get("/info")
    assert response.status_code == 200
    json_data = response.json()
    assert "capabilities" in json_data
    assert "algorithm" in json_data["capabilities"]


def test_cv_info_structure():
    response = client.get("/info")
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "description" in data
    caps = data["capabilities"]
    assert "framework" in caps
    assert "classes" in caps
    assert isinstance(caps["classes"], list)
    assert len(caps["classes"]) == 6


def test_inference_no_file():
    response = client.post("/inference")
    assert response.status_code == 422


def test_inference_with_dummy_image():
    """Testa l'inferenza con un'immagine generata in memoria (64x64 pixel rossi)."""
    from PIL import Image
    img = Image.new("RGB", (64, 64), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/inference",
        files={"file": ("test.png", buf, "image/png")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "confidence" in data
    assert "latency_ms" in data
    assert isinstance(data["confidence"], float)
    assert data["result"] in ["cardboard", "glass", "metal", "paper", "plastic", "trash", "error"]


def test_train_endpoint():
    response = client.post("/train", json={
        "epochs": 1,
        "batch_size": 16,
        "learning_rate": 0.001,
        "dataset_name": "test"
    })
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert "status" in data
    assert data["status"] == "started"


def test_train_status_not_found():
    response = client.get("/train/non_existent_job_id")
    assert response.status_code == 404


def test_train_params_validation():
    response = client.post("/train", json={
        "epochs": "not_a_number"
    })
    assert response.status_code == 422
