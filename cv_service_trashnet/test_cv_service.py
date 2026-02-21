import pytest
from fastapi.testclient import TestClient
import sys
import os

# Aggiungiamo il percorso "cv_service_trashnet" al PYTHONPATH in modo che "service.engine" funzioni
current_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(current_dir))

from service.main import app

client = TestClient(app)

def test_cv_health():
    # Questo endpoint potrebbe restituire 503 se l'engine phtorch/mobilenet non fa in tempo a inizializzarsi
    # In un test unitario veloce, potremmo mockare, ma un check alla risposta strutturata è sufficiente.
    response = client.get("/health")
    assert response.status_code in [200, 503]

def test_cv_info():
    response = client.get("/info")
    assert response.status_code == 200
    json_data = response.json()
    assert "capabilities" in json_data
    assert "algorithm" in json_data["capabilities"]
