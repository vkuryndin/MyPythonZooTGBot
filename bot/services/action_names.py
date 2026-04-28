from bot.states.user_states import ContactStaffState, FeedbackState


def get_cancelled_action_name(
    current_state: str | None,
    quiz_active: bool,
) -> str | None:
    """Return human-readable name of the action being cancelled."""

    if quiz_active:
        return "прохождение викторины"

    if current_state == ContactStaffState.waiting_for_message.state:
        return "сообщение сотруднику зоопарка"

    if current_state == FeedbackState.waiting_for_rating.state:
        return "оценка викторины"

    if current_state == FeedbackState.waiting_for_comment.state:
        return "комментарий к отзыву"

    return None


def build_cancel_text(action_name: str | None) -> str:
    """Build user-facing cancel message."""

    if action_name is None:
        return "Активного действия для отмены не было."

    return f"Отменено действие: {action_name}."