from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile

from bot.handlers.result_view import send_result_actions_menu
from bot.repositories.quiz_result_repository import get_last_quiz_result
from bot.services.image_generation_service import generate_result_image
from bot.services.message_utils import safe_delete_message
from bot.services.rate_limit_service import check_user_cooldown
from bot.services.result_service import get_last_result_animal
from bot.services.user_input_service import get_callback_message


router = Router()

IMAGE_GENERATION_COOLDOWN_SECONDS = 60

GENERATION_PROGRESS_TEXT = (
    "⏳ Генерирую картинку по твоему результату...\n\n"
    "Это может занять немного времени."
)


@router.callback_query(lambda callback: callback.data == "generate_result_image")
async def generate_result_image_handler(callback: CallbackQuery) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    animal = await get_last_result_animal(callback.from_user.id)

    if animal is None:
        await callback.answer("Сначала пройди викторину 🙂")
        return

    allowed, retry_after = await check_user_cooldown(
        user_id=callback.from_user.id,
        action="generate_result_image",
        seconds=IMAGE_GENERATION_COOLDOWN_SECONDS,
    )

    if not allowed:
        await callback.answer(
            "Картинку можно генерировать не чаще одного раза в 60 секунд. "
            f"Подожди ещё {retry_after} сек.",
            show_alert=True,
        )
        return

    await callback.answer("Начинаю генерацию картинки 🐾")

    result = await get_last_quiz_result(callback.from_user.id)
    image_tags = result.get("image_tags", []) if result else []

    try:
        if message.photo:
            await message.edit_caption(
                caption=GENERATION_PROGRESS_TEXT,
                reply_markup=None,
            )
        else:
            await message.edit_text(
                text=GENERATION_PROGRESS_TEXT,
                reply_markup=None,
            )
    except TelegramBadRequest:
        pass

    generated_image_path = await generate_result_image(
        animal=animal,
        image_tags=image_tags,
    )

    await safe_delete_message(message)

    if generated_image_path is None:
        await message.answer(
            "Сейчас не удалось сгенерировать картинку. Попробуй позже 🐾"
        )

        await send_result_actions_menu(
            message=message,
            animal=animal,
            include_view_result_button=True,
        )
        return

    await message.answer_photo(
        photo=FSInputFile(generated_image_path),
        caption=f"AI-картинка по твоему результату: {animal['name']} 🐾",
    )

    await send_result_actions_menu(
        message=message,
        animal=animal,
        include_view_result_button=True,
    )