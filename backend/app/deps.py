import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings
from app.storage import ImageStorage


def get_storage(request: Request) -> ImageStorage:
    return request.app.state.storage


def require_internal_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    if x_internal_token is None or not secrets.compare_digest(
        x_internal_token, settings.internal_api_token
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")
