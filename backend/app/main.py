from fastapi import FastAPI

app = FastAPI(
    title = "ChainTrace API",
    description="Blockchain-backed ML provenance and verification platform",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    return{
        "status": "ok",
        "service": "ChainTrace API"
    }