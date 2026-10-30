import io
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.api_client import BackendClient, BackendError
from app.config import Settings
from app.filters import IsAdmin
from app.handlers.common import GREETING
from app.keyboards import CREATE_PRODUCT_BUTTON, admin_keyboard, catalog_keyboard

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())

MAX_TITLE_LENGTH = 255
MAX_FILE_SIZE = 10 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

HOW_TO_CREATE = (
    "Отправьте одним сообщением фото товара с подписью.\n"
    "Первая строка подписи — название, остальные строки (необязательно) — описание."
)

TITLE_PREFIX = re.compile(r"^\s*(название|name)\s*:\s*", re.IGNORECASE)


def parse_caption(caption: str) -> tuple[str, str | None]:
    """First non-empty line is the title, the rest is the description."""
    lines = caption.strip().splitlines()
    title = TITLE_PREFIX.sub("", lines[0]).strip() if lines else ""
    description = "\n".join(lines[1:]).strip() or None
    return title, description


@router.message(CommandStart())
async def admin_start(message: Message, settings: Settings) -> None:
    await message.answer(GREETING, reply_markup=catalog_keyboard(settings.webapp_url))
    await message.answer(
        f"Вы администратор. Чтобы добавить товар, нажмите «{CREATE_PRODUCT_BUTTON}».",
        reply_markup=admin_keyboard(),
    )


@router.message(Command("create"))
@router.message(F.text == CREATE_PRODUCT_BUTTON)
async def create_hint(message: Message) -> None:
    await message.answer(HOW_TO_CREATE)


@router.message(F.photo, F.caption)
async def create_from_photo(message: Message, bot: Bot, api: BackendClient, settings: Settings) -> None:
    if not message.photo:
        return
    # Telegram sends several sizes, the last one is the largest; photos are always JPEG.
    await save_product(message, bot, api, settings, message.photo[-1].file_id, "image/jpeg")


@router.message(F.document.mime_type.in_(IMAGE_TYPES), F.caption)
async def create_from_document(
    message: Message, bot: Bot, api: BackendClient, settings: Settings
) -> None:
    document = message.document
    if document is None or document.mime_type is None:
        return
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.answer("Файл слишком большой, максимум 10 МБ.")
        return
    await save_product(message, bot, api, settings, document.file_id, document.mime_type)


@router.message(F.photo | F.document.mime_type.in_(IMAGE_TYPES))
async def image_without_caption(message: Message) -> None:
    await message.answer("Не вижу названия. " + HOW_TO_CREATE)


async def save_product(
    message: Message,
    bot: Bot,
    api: BackendClient,
    settings: Settings,
    file_id: str,
    content_type: str,
) -> None:
    title, description = parse_caption(message.caption or "")
    if not title:
        await message.answer("Название не может быть пустым. " + HOW_TO_CREATE)
        return
    if len(title) > MAX_TITLE_LENGTH:
        await message.answer(
            f"Название (первая строка подписи) слишком длинное, максимум {MAX_TITLE_LENGTH} символов."
        )
        return

    image = io.BytesIO()
    await bot.download(file_id, destination=image)
    try:
        product = await api.create_product(
            title=title,
            description=description,
            image=image.getvalue(),
            content_type=content_type,
            idempotency_key=f"tg:{message.chat.id}:{message.message_id}",
        )
    except BackendError:
        logger.exception("Failed to create product from message %s", message.message_id)
        await message.answer("Не удалось сохранить товар, попробуйте ещё раз позже.")
        return

    await message.answer(
        f"Товар «{product.title}» добавлен в каталог.",
        reply_markup=catalog_keyboard(settings.webapp_url),
    )
