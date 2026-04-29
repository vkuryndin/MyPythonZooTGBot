from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.handlers.menu import show_main_menu
from bot.handlers.result_view import show_last_result
from bot.services.action_names import build_cancel_text, get_cancelled_action_name
from bot.services.message_utils import safe_delete_callback_message
from bot.services.user_input_service import get_callback_message


router = Router()


@router.callback_query(lambda callback: callback.data == "cancel_action")
async def cancel_action_handler(callback: CallbackQuery, state: FSMContext) -> None:
    message = get_callback_message(callback)

    if message is None:
        await callback.answer("Сообщение уже недоступно 🙂")
        return

    current_state = await state.get_state()
    data = await state.get_data()

    action_name = get_cancelled_action_name(
        current_state=current_state,
        quiz_active=False,
    )
    cancel_text = build_cancel_text(action_name)
    return_to_result = data.get("return_to_result", True)

    await safe_delete_callback_message(callback)
    await state.clear()

    await message.answer(cancel_text)

    if return_to_result:
        await show_last_result(
            message=message,
            user_id=callback.from_user.id,
        )
    else:
        await show_main_menu(
            message=message,
            user_id=callback.from_user.id,
        )

    await callback.answer()


@router.callback_query(
    lambda callback: bool(
        callback.data
        and (
            callback.data.startswith("feedback_rating:")
            or callback.data in {
                "skip_feedback_comment",
                "feedback_change_rating",
                "feedback_reply_method:none",
                "feedback_back_to_reply_method",
            }
        )
    )
)
async def stale_feedback_action_handler(callback: CallbackQuery) -> None:
    await safe_delete_callback_message(callback)
    await callback.answer("Это действие уже неактуально 🙂")