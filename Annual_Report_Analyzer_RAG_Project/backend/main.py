from fastapi import FastAPI
from app.config import settings  # noqa: F401

app = FastAPI(title="Annual Report Analyzer", version="0.1.0")
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}