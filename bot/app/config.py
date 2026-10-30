from functools import lru_cache
from typing import Annotated, Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr
    admin_ids: Annotated[frozenset[int], NoDecode] = frozenset()

    webhook_base_url: str
    webhook_path: str = "/tg/webhook"
    webhook_secret: SecretStr

    webapp_url: str

    backend_url: str = "http://backend:8000"
    internal_api_token: SecretStr

    host: str = "0.0.0.0"
    port: int = 8080

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: Any) -> Any:
        if isinstance(value, str):
            return frozenset(int(part) for part in value.split(",") if part.strip())
        return value

    @property
    def webhook_url(self) -> str:
        return self.webhook_base_url.rstrip("/") + self.webhook_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
