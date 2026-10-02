from app.db.database import SessionLocal
from app.models.market_asset import MarketAsset
from app.models.opportunity import Opportunity


def create_user(client, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={
            "first_name": "Test",
            "last_name": "User",
            "email": email,
            "password": "StrongPassword123!",
            "country": "KE",
        },
    )
    assert response.status_code == 201, response.text
    response = client.post("/auth/login", json={"email": email, "password": "StrongPassword123!"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_watchlists_alerts_and_opportunity_reviews_are_user_scoped(client):
    first_token = create_user(client, "intelligence.one@example.com")
    second_token = create_user(client, "intelligence.two@example.com")
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}

    with SessionLocal() as db:
        asset = MarketAsset(
            symbol="TEST1",
            name="Test Instrument",
            asset_type="EQUITY",
            exchange="TEST",
            country_code="KE",
            currency_code="KES",
            provider="test-only",
        )
        db.add(asset)
        opportunity = Opportunity(
            opportunity_type="MARKET_EVENT",
            title="Test-only event",
            summary="Synthetic fixture used only to verify access controls.",
            source="test fixture",
            verification_status="UNVERIFIED",
            event_fingerprint="test-event-unique-1",
        )
        db.add(opportunity)
        db.commit()
        db.refresh(asset)
        db.refresh(opportunity)
        asset_id = asset.id
        opportunity_id = opportunity.id

    response = client.post("/api/watchlists", headers=first_headers, json={"name": "Global watchlist"})
    assert response.status_code == 201, response.text
    watchlist_id = response.json()["id"]

    response = client.get("/api/watchlists", headers=second_headers)
    assert response.status_code == 200
    assert response.json() == []

    response = client.post(
        f"/api/watchlists/{watchlist_id}/items",
        headers=first_headers,
        json={"market_asset_id": asset_id},
    )
    assert response.status_code == 201, response.text

    response = client.post(
        "/api/alert-rules",
        headers=first_headers,
        json={"market_asset_id": asset_id, "category": "PRICE_ALERT", "condition_type": "PERCENT_CHANGE", "threshold": "5.0"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["threshold"] == "5.00000000"

    response = client.get("/api/opportunities", headers=first_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.put(
        f"/api/opportunities/{opportunity_id}/review",
        headers=first_headers,
        json={"status": "SAVED", "user_notes": "Review official source later."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SAVED"

    response = client.get("/api/watchlists/{watchlist_id}/items".format(watchlist_id=watchlist_id), headers=second_headers)
    assert response.status_code == 404
