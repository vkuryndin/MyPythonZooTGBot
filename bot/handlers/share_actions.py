from urllib.parse import urlencode

from aiogram import Router
from aiogram.types import CallbackQuery

from bot.config import settings
from bot.keyboards.action_keyboards import get_share_result_keyboard
from bot.services.message_utils import safe_delete_callback_message
from bot.services.result_service import get_last_result_animal
from bot.services.user_input_service import get_callback_message


router = Router()


@router.callback_query(lambda callback: callback.data == "share_result")
async def share_result_handler(callback: CallbackQuery) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    animal = await get_last_result_animal(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    await safe_delete_callback_message(callback)

    share_text = (
        f"Моё тотемное животное в Московском зоопарке — {animal['name']}! 🐾\n\n"
        "Пройди викторину и узнай своё тотемное животное."
    )
    full_share_text = f"{share_text}\n\n{settings.bot_link}"

    telegram_share_url = "https://t.me/share/url?" + urlencode(
        {
            "url": settings.bot_link,
            "text": share_text,
        }
    )
    vk_share_url = "https://vk.com/share.php?" + urlencode(
        {
            "url": settings.bot_link,
        }
    )
    whatsapp_share_url = "https://api.whatsapp.com/send?" + urlencode(
        {
            "text": full_share_text,
        }
    )
    max_share_url = "https://max.ru/:share?" + urlencode(
        {
            "text": full_share_text,
        }
    )

    keyboard = get_share_result_keyboard(
        telegram_share_url=telegram_share_url,
        vk_share_url=vk_share_url,
        whatsapp_share_url=whatsapp_share_url,
        max_share_url=max_share_url,
    )

    await message.answer(
        "Выбери, где хочешь поделиться результатом 👇",
        reply_markup=keyboard,
    )
    await callback.answer()