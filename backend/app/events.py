"""Fan-out of "product created" events to SSE clients.

Every backend instance keeps one LISTEN connection to PostgreSQL. Whichever instance
creates a product sends NOTIFY in the same transaction, so all instances (and all their
SSE clients) receive it. No state is shared between instances except PostgreSQL itself.
"""
import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager

import asyncpg

logger = logging.getLogger(__name__)

CHANNEL = "products"
# Sent to clients after the LISTEN connection was re-established: events may have been missed.
RESYNC = object()
RESYNC_MESSAGE = '{"type":"resync"}'

HEALTHCHECK_INTERVAL = 30
RECONNECT_DELAY = 2


class ProductEvents:
    def __init__(self, database_url: str) -> None:
        # SQLAlchemy URL -> plain asyncpg DSN
        self._dsn = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        self._subscribers: set[asyncio.Queue[object]] = set()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._listen_forever())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue[object]]:
        queue: asyncio.Queue[object] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def _publish(self, item: object) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(item)
            except asyncio.QueueFull:
                # Slow client: tell it to reload the list instead of growing the queue.
                queue.get_nowait()
                queue.put_nowait(RESYNC)

    def _on_notify(self, _conn: object, _pid: int, _channel: str, payload: str) -> None:
        self._publish(payload)

    async def _listen_forever(self) -> None:
        first = True
        while True:
            try:
                conn = await asyncpg.connect(self._dsn)
                try:
                    await conn.add_listener(CHANNEL, self._on_notify)
                    if not first:
                        self._publish(RESYNC)
                    first = False
                    logger.info("Listening for product events")
                    while True:
                        await asyncio.sleep(HEALTHCHECK_INTERVAL)
                        await conn.execute("SELECT 1")
                finally:
                    await conn.close(timeout=2)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Product events connection lost, reconnecting", exc_info=True)
            await asyncio.sleep(RECONNECT_DELAY)
