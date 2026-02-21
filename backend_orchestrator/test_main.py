import pytest
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend_orchestrator.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert "status" in json_data
    assert json_data["status"] == "ok"
    assert "docker_connected" in json_data

def test_list_containers_unavailable():
    # Se il test gira senza permessi docker potrebbe dare 503, validiamolo
    response = client.get("/containers")
    assert response.status_code in [200, 503]
