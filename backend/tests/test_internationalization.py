def test_reference_data_exists(client):
    countries = client.get("/countries")
    assert countries.status_code == 200, countries.text
    country_codes = {item["country_code"] for item in countries.json()}
    assert {"KE", "US", "GB"}.issubset(country_codes)

    currencies = client.get("/currencies")
    assert currencies.status_code == 200, currencies.text
    currency_codes = {item["code"] for item in currencies.json()}
    assert {"KES", "USD", "EUR", "JPY"}.issubset(currency_codes)


def test_user_international_settings_update(client):
    payload = {
        "first_name": "Grace",
        "last_name": "Wanjiku",
        "email": "grace.wanjiku@example.com",
        "phone": "+254712345678",
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
    token = login_response.json()["access_token"]

    response = client.put(
        "/settings/international",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "country_code": "US",
            "primary_currency": "USD",
            "timezone": "America/New_York",
            "locale": "en_US",
            "date_format": "MM/DD/YYYY",
            "time_format": "12h",
            "number_format": "#,##0.00",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["country_code"] == "US"
    assert body["primary_currency"] == "USD"
    assert body["timezone"] == "America/New_York"
    assert body["locale"] == "en_US"


def test_registration_uses_selected_country_defaults(client):
    payload = {
        "first_name": "Aiko",
        "last_name": "Tanaka",
        "email": "aiko.tanaka@example.com",
        "password": "StrongPassword123!",
        "country": "JP",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["currency"] == "JPY"
    assert body["timezone"] == "Asia/Tokyo"
    assert body["locale"] == "ja_JP"
    assert body["language"] == "ja"
