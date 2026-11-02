from io import BytesIO
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.storage.storage import LocalStorageProvider


def test_production_settings_reject_default_jwt_secrets():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret="change-me",
            jwt_refresh_secret="change-me-refresh",
        )


def test_production_settings_require_distinct_strong_secrets():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret="a" * 40,
            jwt_refresh_secret="a" * 40,
        )

    settings = Settings(
        app_env="production",
        jwt_secret="a" * 40,
        jwt_refresh_secret="b" * 40,
    )
    assert settings.app_env == "production"


def test_local_storage_rejects_paths_outside_storage_root(tmp_path):
    storage = LocalStorageProvider(str(tmp_path / "storage"))
    with pytest.raises(ValueError, match="inside"):
        storage.upload_file(
            file_name="../outside.txt",
            content=BytesIO(b"should not be written"),
            content_type="text/plain",
        )


def test_profile_photo_uses_server_filename_and_enforces_size(client, monkeypatch, tmp_path):
    storage_root = tmp_path / "profile-storage"
    monkeypatch.setattr(
        "app.api.routes.profile.get_storage_provider",
        lambda: LocalStorageProvider(str(storage_root)),
    )
    payload = {
        "first_name": "Amina",
        "last_name": "Upload",
        "email": "amina.upload@example.com",
        "password": "StrongPassword123!",
        "country": "KE",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    login = client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    upload = client.post(
        "/profile/photo",
        headers=headers,
        files={"file": ("../../escape.png", b"\x89PNG\r\n\x1a\nimage-data", "image/png")},
    )
    assert upload.status_code == 200
    image_path = Path(upload.json()["image_url"])
    assert image_path.resolve().is_relative_to(storage_root.resolve())
    assert image_path.name != "escape.png"
    assert not (tmp_path / "escape.png").exists()

    oversized = client.post(
        "/profile/photo",
        headers=headers,
        files={"file": ("large.png", b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024), "image/png")},
    )
    assert oversized.status_code == 413
