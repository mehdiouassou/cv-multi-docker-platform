import pytest
from unittest.mock import patch, MagicMock
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
    response = client.get("/containers")
    assert response.status_code in [200, 503]


def test_start_container_no_docker():
    response = client.post("/containers/fake_id/start")
    assert response.status_code in [404, 500, 503]


def test_stop_container_no_docker():
    response = client.post("/containers/fake_id/stop")
    assert response.status_code in [404, 500, 503]


def test_delete_container_no_docker():
    response = client.delete("/containers/fake_id")
    assert response.status_code in [404, 500, 503]


def test_get_stats_no_docker():
    response = client.get("/containers/fake_id/stats")
    assert response.status_code in [404, 500, 503]


def test_get_logs_no_docker():
    response = client.get("/containers/fake_id/logs")
    assert response.status_code in [403, 404, 500, 503]


def test_create_service_missing_template():
    payload = {
        "service_name": "test_service_xyz",
        "template_name": "template_that_does_not_exist",
        "cpu_cores": 1.0,
        "mem_limit_mb": 512
    }
    response = client.post("/services/create", json=payload)
    # Senza Docker o col template mancante ci aspettiamo un errore
    assert response.status_code in [400, 503]


def test_create_service_validation():
    # Richiesta senza service_name (campo obbligatorio)
    payload = {
        "template_name": "template_service"
    }
    response = client.post("/services/create", json=payload)
    assert response.status_code == 422


def test_health_returns_correct_structure():
    response = client.get("/health")
    data = response.json()
    assert isinstance(data["status"], str)
    assert isinstance(data["docker_connected"], bool)
