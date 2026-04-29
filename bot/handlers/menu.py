from pathlib import Path

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.keyboards.main_menu import (
    get_back_to_main_menu_keyboard,
    get_back_to_result_keyboard,
    get_main_menu_keyboard,
)
from bot.services.message_utils import safe_delete_callback_message
from bot.services.result_service import has_last_result


router = Router()

BASE_DIR = Path(__file__).resolve().parents[2]
LOGO_PATH = BASE_DIR / "assets" / "images" / "mz_logo.jpg"


FIRST_START_TEXT = (
    "Привет! 🐾\n\n"
    "Добро пожаловать в небольшую викторину Московского зоопарка.\n\n"
    "Сейчас мы узнаем, кто тебе ближе по характеру: загадочный манул, "
    "дружный сурикат, спокойный слон или кто-то ещё из обитателей зоопарка.\n\n"
    "Отвечай на вопросы — а в конце я покажу твоё тотемное животное."
)

REPEAT_START_TEXT = (
    "С возвращением в Московский зоопарк! 🐾\n\n"
    "Твоё тотемное животное уже ждёт тебя. Можно вернуться к результату, "
    "поделиться им с друзьями, узнать про опеку или пройти викторину ещё раз.\n\n"
    "Что делаем?"
)

COMMANDS_TEXT = (
    "\n\nКоманды управления:\n"
    "/help — справка\n"
    "/result — последний результат\n"
    "/cancel — отменить текущее действие"
)

MAIN_MENU_TEXT = (
    "Главное меню 🐾\n\n"
    "Выбери, что хочешь сделать:"
)

ABOUT_ADOPTION_TEXT = (
    "🐾 О программе опеки\n\n"
    "В Московском зоопарке можно взять животное под опеку и помогать "
    "заботиться о его питании, уходе и условиях жизни.\n\n"
    "Это способ поддержать зоопарк и внести вклад в сохранение "
    "биоразнообразия.\n\n"
    "Если хочешь узнать подробнее, можешь связаться с сотрудником "
    "зоопарка после прохождения викторины."
)


async def show_start_screen(message: Message) -> None:
    """Show start screen with different text for new and returning users."""

    user_id = message.from_user.id
    user_has_result = await has_last_result(user_id)

    text = REPEAT_START_TEXT if user_has_result else FIRST_START_TEXT
    keyboard = get_main_menu_keyboard(has_result=user_has_result)

    await send_menu_message(
        message=message,
        text=f"{text}{COMMANDS_TEXT}",
        has_result=user_has_result,
        use_logo=True,
    )


async def show_main_menu(
    message: Message,
    user_id: int,
    text: str | None = None,
    include_home_button: bool = False,
) -> None:
    """Send main menu with dynamic buttons."""

    user_has_result = await has_last_result(user_id)

    await message.answer(
        text or MAIN_MENU_TEXT,
        reply_markup=get_main_menu_keyboard(
            has_result=user_has_result,
            include_home_button=include_home_button,
        ),
    )


async def send_menu_message(
    message: Message,
    text: str,
    has_result: bool,
    use_logo: bool = False,
) -> None:
    """Send menu message with optional logo."""

    keyboard = get_main_menu_keyboard(has_result=has_result)

    if use_logo and LOGO_PATH.exists():
        await message.answer_photo(
            photo=FSInputFile(LOGO_PATH),
            caption=text,
            reply_markup=keyboard,
        )
        return

    await message.answer(
        text,
        reply_markup=keyboard,
    )


@router.callback_query(lambda callback: callback.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Show main menu."""

    await state.clear()
    await safe_delete_callback_message(callback)

    await show_main_menu(
        message=callback.message,
        user_id=callback.from_user.id,
    )
    await callback.answer()


@router.callback_query(
    lambda callback: callback.data in {
        "about_adoption",
        "about_adoption:main",
        "about_adoption:result",
    }
)
async def about_adoption_handler(callback: CallbackQuery) -> None:
    """Show information about the animal adoption program."""

    is_from_result = callback.data == "about_adoption:result"

    await safe_delete_callback_message(callback)

    await callback.message.answer(
        ABOUT_ADOPTION_TEXT,
        reply_markup=(
            get_back_to_result_keyboard()
            if is_from_result
            else get_back_to_main_menu_keyboard()
        ),
    )
    await callback.answer()