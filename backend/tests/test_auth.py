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
