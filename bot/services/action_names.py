from bot.states.user_states import ContactStaffState, FeedbackState


CONTACT_STATES = {
    ContactStaffState.waiting_for_reply_method.state,
    ContactStaffState.waiting_for_reply_contact.state,
    ContactStaffState.waiting_for_message.state,
}

FEEDBACK_STATES = {
    FeedbackState.waiting_for_rating.state,
    FeedbackState.waiting_for_comment.state,
    FeedbackState.waiting_for_reply_method.state,
    FeedbackState.waiting_for_reply_contact.state,
}


def get_cancelled_action_name(
    current_state: str | None,
    quiz_active: bool,
) -> str | None:
    """Return human-readable name of the action being cancelled."""

    if quiz_active:
        return "прохождение викторины"

    if current_state in CONTACT_STATES:
        return "сообщение сотруднику зоопарка"

    if current_state in FEEDBACK_STATES:
        return "отзыв о викторине"

    return None


def build_cancel_text(action_name: str | None) -> str:
    """Build user-facing cancel message."""

    if action_name is None:
        return "Активного действия для отмены не было."

    return f"Отменено действие: {action_name}."