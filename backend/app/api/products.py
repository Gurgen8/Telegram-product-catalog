import asyncio
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.deps import get_storage, require_internal_token
from app.events import CHANNEL, RESYNC, RESYNC_MESSAGE, ProductEvents
from app.models import Product
from app.schemas import ProductOut, ProductPage
from app.storage import ImageStorage

router = APIRouter(prefix="/products", tags=["products"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
StorageDep = Annotated[ImageStorage, Depends(get_storage)]

WS_PING_INTERVAL = 20


def to_schema(product: Product, storage: ImageStorage) -> ProductOut:
    return ProductOut(
        id=product.id,
        title=product.title,
        description=product.description,
        image_url=storage.public_url(product.image_key),
        created_at=product.created_at,
    )


@router.get("", response_model=ProductPage)
async def list_products(
    session: SessionDep,
    storage: StorageDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductPage:
    total = await session.scalar(select(func.count()).select_from(Product))
    products = await session.scalars(
        select(Product).order_by(Product.id.desc()).limit(limit).offset(offset)
    )
    return ProductPage(items=[to_schema(p, storage) for p in products], total=total or 0)


@router.websocket("/ws")
async def products_ws(websocket: WebSocket) -> None:
    """Pushes catalog changes as JSON messages.

    {"type": "product", "product": {...}} - product created
    {"type": "deleted", "ids": [...]}     - products deleted (DB trigger, any source)
    {"type": "resync"}                    - reload the whole list
    """
    events: ProductEvents = websocket.app.state.events
    await websocket.accept()
    try:
        with events.subscribe() as queue:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=WS_PING_INTERVAL)
                except TimeoutError:
                    # Keeps proxies from closing an idle connection and detects dead clients.
                    await websocket.send_text('{"type":"ping"}')
                    continue
                # NOTIFY payloads are already complete client messages.
                await websocket.send_text(RESYNC_MESSAGE if item is RESYNC else str(item))
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass


async def find_by_external_id(session: AsyncSession, external_id: str) -> Product | None:
    return await session.scalar(select(Product).where(Product.external_id == external_id))


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_token)],
)
async def create_product(
    response: Response,
    session: SessionDep,
    storage: StorageDep,
    settings: Annotated[Settings, Depends(get_settings)],
    title: Annotated[str, Form(max_length=255)],
    image: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form(max_length=2000)] = None,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
) -> ProductOut:
    title = title.strip()
    if not title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Title must not be empty")
    description = (description or "").strip() or None

    # Telegram may redeliver the same update; return the product created the first time.
    if idempotency_key:
        existing = await find_by_external_id(session, idempotency_key)
        if existing:
            response.status_code = status.HTTP_200_OK
            return to_schema(existing, storage)

    content_type = image.content_type
    if content_type is None or not storage.is_supported(content_type):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported image type")

    data = await image.read(settings.max_image_size + 1)
    if len(data) > settings.max_image_size:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Image is empty")

    key = await storage.put(data, content_type)

    stmt = (
        insert(Product)
        .values(title=title, description=description, image_key=key, external_id=idempotency_key)
        .on_conflict_do_nothing(index_elements=[Product.external_id])
        .returning(Product)
    )
    try:
        product = (await session.scalars(stmt)).one_or_none()
        if product is not None:
            # Delivered to every backend instance only after the commit succeeds.
            payload = f'{{"type":"product","product":{to_schema(product, storage).model_dump_json()}}}'
            await session.execute(select(func.pg_notify(CHANNEL, payload)))
        await session.commit()
    except Exception:
        await storage.delete(key)
        raise

    if product is None:
        # Another instance won the race for the same idempotency key.
        await storage.delete(key)
        existing = await find_by_external_id(session, idempotency_key) if idempotency_key else None
        if existing is None:
            # The concurrently created product was deleted in the meantime.
            raise HTTPException(status.HTTP_409_CONFLICT, "Product was created concurrently and then deleted")
        response.status_code = status.HTTP_200_OK
        product = existing

    return to_schema(product, storage)
