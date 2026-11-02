def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_and_login_flow(client):
    payload = {
        "first_name": "Jane",
        "last_name": "Njeri",
        "email": "jane.njeri@example.com",
        "phone": "+254700000001",
        "password": "StrongPassword123!",
        "country": "KE",
        "currency": "KES",
        "timezone": "Africa/Nairobi",
    }

    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201, register_response.text

    login_response = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login_response.status_code == 200, login_response.text
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == payload["email"].lower()


def test_refresh_rotates_tokens_and_logout_revokes_access(client):
    payload = {
        "first_name": "Amina",
        "last_name": "Test",
        "email": "amina.session@example.com",
        "password": "StrongPassword123!",
        "country": "KE",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    original = login.json()

    refreshed = client.post("/auth/refresh", json={"refresh_token": original["refresh_token"]})
    assert refreshed.status_code == 200
    rotated = refreshed.json()
    assert rotated["refresh_token"] != original["refresh_token"]
    assert client.post("/auth/refresh", json={"refresh_token": original["refresh_token"]}).status_code == 401

    headers = {"Authorization": f"Bearer {rotated['access_token']}"}
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]}).status_code == 401
