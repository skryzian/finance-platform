from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.ai import router as ai_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.international import router as international_router
from app.api.routes.markets import router as markets_router
from app.api.routes.profile import router as profile_router
from app.api.routes.watchlists import router as watchlists_router
from app.core.config import settings
from app.db.database import Base, engine
import app.models
from app.seed.reference_data import seed_reference_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_reference_data()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}


app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(profile_router)
app.include_router(international_router)
app.include_router(markets_router)
app.include_router(watchlists_router)
app.include_router(intelligence_router)
