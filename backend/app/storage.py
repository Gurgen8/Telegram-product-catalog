import io
import logging
import uuid

from minio import Minio
from minio.error import S3Error
from starlette.concurrency import run_in_threadpool

from app.config import Settings

logger = logging.getLogger(__name__)

EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class ImageStorage:
    def __init__(self, settings: Settings) -> None:
        self._client = Minio(
            settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
        )
        self._bucket = settings.s3_bucket
        self._public_url = settings.media_public_url.rstrip("/")

    @staticmethod
    def is_supported(content_type: str | None) -> bool:
        return content_type in EXTENSIONS

    async def put(self, data: bytes, content_type: str) -> str:
        key = uuid.uuid4().hex + EXTENSIONS[content_type]
        await run_in_threadpool(
            self._client.put_object,
            self._bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type=content_type,
        )
        return key

    async def delete(self, key: str) -> None:
        try:
            await run_in_threadpool(self._client.remove_object, self._bucket, key)
        except S3Error:
            logger.warning("Failed to remove orphan object %s", key, exc_info=True)

    def public_url(self, key: str) -> str:
        return f"{self._public_url}/{key}"
