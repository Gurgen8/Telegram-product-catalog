from dataclasses import dataclass

import aiohttp


class BackendError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CreatedProduct:
    id: int
    title: str


class BackendClient:
    def __init__(self, base_url: str, token: str, timeout: float = 20) -> None:
        self._base_url = base_url
        self._token = token
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            base_url=self._base_url,
            headers={"X-Internal-Token": self._token},
            timeout=self._timeout,
        )

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def create_product(
        self,
        title: str,
        description: str | None,
        image: bytes,
        content_type: str,
        idempotency_key: str,
    ) -> CreatedProduct:
        assert self._session, "client is not started"

        form = aiohttp.FormData()
        form.add_field("title", title)
        if description:
            form.add_field("description", description)
        form.add_field("image", image, filename="image", content_type=content_type)

        try:
            async with self._session.post(
                "/api/products", data=form, headers={"Idempotency-Key": idempotency_key}
            ) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    raise BackendError(f"backend responded {resp.status}: {body[:300]}")
                payload = await resp.json()
        except aiohttp.ClientError as exc:
            raise BackendError(str(exc)) from exc

        return CreatedProduct(id=payload["id"], title=payload["title"])
