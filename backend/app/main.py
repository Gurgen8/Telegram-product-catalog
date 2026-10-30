import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.products import router as products_router
from app.config import get_settings
from app.db import engine
from app.events import ProductEvents
from app.storage import ImageStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.storage = ImageStorage(settings)
    app.state.events = ProductEvents(settings.database_url)
    await app.state.events.start()
    yield
    await app.state.events.stop()
    await engine.dispose()


app = FastAPI(title="Catalog API", lifespan=lifespan)
app.include_router(products_router, prefix="/api")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}
