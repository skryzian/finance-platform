import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-only-access-secret"
os.environ["JWT_REFRESH_SECRET"] = "test-only-refresh-secret"

import pytest
from fastapi.testclient import TestClient

from app.db.database import Base, engine
import app.models
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
