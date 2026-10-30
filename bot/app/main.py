import asyncio
import logging
import sys
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.methods import TelegramMethod
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.api_client import BackendClient
from app.config import Settings, get_settings
from app.handlers import admin, common

logger = logging.getLogger(__name__)


def build_dispatcher(settings: Settings) -> Dispatcher:
    api = BackendClient(settings.backend_url, settings.internal_api_token.get_secret_value())

    dp = Dispatcher(settings=settings, api=api)
    # Admin router goes first so admin-only handlers win over the generic reply.
    dp.include_routers(admin.router, common.router)
    dp.startup.register(api.start)
    dp.shutdown.register(api.close)
    return dp


class WebhookHandler(SimpleRequestHandler):
    """Replies with an empty 200 when there is no method to return.

    aiogram answers with an empty multipart body in that case, which Telegram rejects
    ("unexpected end of request content") and then redelivers the same update.
    """

    async def _handle_request(self, bot: Bot, request: web.Request) -> web.Response:
        result: TelegramMethod[Any] | None = await self.dispatcher.feed_webhook_update(
            bot, await request.json(loads=bot.session.json_loads), **self.data
        )
        if result is None:
            return web.Response()
        return web.Response(body=self._build_response_writer(bot=bot, result=result))


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def serve(settings: Settings) -> None:
    bot = Bot(settings.bot_token.get_secret_value())
    dp = build_dispatcher(settings)

    app = web.Application()
    # handle_in_background=False: Telegram gets 200 only after the update is processed,
    # so if an instance dies mid-request the update is redelivered to another one.
    WebhookHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret.get_secret_value(),
        handle_in_background=False,
    ).register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)
    app.router.add_get("/health", health)

    web.run_app(app, host=settings.host, port=settings.port, print=None)


async def set_webhook(settings: Settings) -> None:
    dp = build_dispatcher(settings)
    async with Bot(settings.bot_token.get_secret_value()) as bot:
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret.get_secret_value(),
            allowed_updates=dp.resolve_used_update_types(),
        )
    logger.info("Webhook set to %s", settings.webhook_url)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    command = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if command == "serve":
        serve(settings)
    elif command == "set-webhook":
        asyncio.run(set_webhook(settings))
    else:
        sys.exit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
