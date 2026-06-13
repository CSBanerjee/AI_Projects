from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.api.middleware import add_middleware
from app.config import settings
from app.utils import db
from app.store import vector_store
from app.utils.logger import get_logger
import uvicorn

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    settings.validate()
    db.init_db()
    count = vector_store.count()
    log.info(f"RAG service ready. Chunks loaded: {count}")
    yield
    # shutdown
    log.info("RAG service shutting down.")


app = FastAPI(
    title="RAG Analytics Assistant",
    version="1.0.0",
    lifespan=lifespan
)

add_middleware(app)
app.include_router(router)

# serve frontend from root — GET / returns index.html
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)