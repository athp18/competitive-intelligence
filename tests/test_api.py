"""API integration smoke tests using TestClient (no real DB)."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_requires_api_key(client):
    resp = client.get("/targets")
    assert resp.status_code == 403


def test_targets_with_key(client):
    with patch("db.queries.list_targets", new_callable=AsyncMock, return_value=[]):
        resp = client.get("/targets", headers={"X-API-Key": "changeme-dev-key"})
    assert resp.status_code == 200
    assert resp.json() == []
