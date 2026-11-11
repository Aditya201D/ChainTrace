
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import Base, engine

# Import models so SQLAlchemy discovers their table definitions.
from app.models.artifact import ArtifactRecord

from app.api.artifacts import router as artifact_router
from app.api.blockchain import router as blockchain_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Create database tables on application startup.
    Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(
    title="ChainTrace API",
    description=(
        "Blockchain-backed ML supply chain "
        "provenance and verification platform."
    ),
    version="0.2.0",
    lifespan=lifespan
)


app.include_router(artifact_router)
app.include_router(blockchain_router)


@app.get("/health")
def health_check():

    return {
        "status": "ok",
        "service": "ChainTrace API"
    }
