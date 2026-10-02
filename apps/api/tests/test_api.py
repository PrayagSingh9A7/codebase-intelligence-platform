from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_auth_signup_and_me():
    email = "test-ci-platform@example.com"
    response = client.post("/api/auth/signup", json={"name":"Test User","email":email,"password":"password123"})
    assert response.status_code in (200, 409)
    if response.status_code == 409:
        response = client.post("/api/auth/login", json={"email":email,"password":"password123"})
    token = response.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization":f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == email
    client.post("/api/auth/logout", headers={"Authorization":f"Bearer {token}"})
