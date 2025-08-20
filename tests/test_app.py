import pytest

from app import app   # importa la tua Flask app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_homepage(client):
    """Verifica che la homepage risponda 200"""
    response = client.get("/")
    assert response.status_code == 200
