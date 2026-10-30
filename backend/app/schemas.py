from datetime import datetime

from pydantic import BaseModel


class ProductOut(BaseModel):
    id: int
    title: str
    description: str | None
    image_url: str
    created_at: datetime


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
