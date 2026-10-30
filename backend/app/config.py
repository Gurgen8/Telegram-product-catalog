from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "products"
    s3_secure: bool = False

    # Base URL the browser uses to load images, e.g. https://example.com/media
    media_public_url: str

    # Shared secret for write endpoints (used by the bot)
    internal_api_token: str

    max_image_size: int = 10 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
