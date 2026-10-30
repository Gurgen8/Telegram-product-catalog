from aiogram import Router
from aiogram.types import Message

from app.config import Settings
from app.keyboards import catalog_keyboard

router = Router(name="common")

GREETING = "У меня есть товар"


@router.message()
async def greet(message: Message, settings: Settings) -> None:
    await message.answer(GREETING, reply_markup=catalog_keyboard(settings.webapp_url))
