from aiogram.fsm.state import State, StatesGroup


class ContactStaffState(StatesGroup):
    """States for contacting zoo staff."""

    waiting_for_reply_method = State()
    waiting_for_reply_contact = State()
    waiting_for_message = State()

class FeedbackState(StatesGroup):
    """States for collecting user feedback."""

    waiting_for_rating = State()
    waiting_for_comment = State()
    waiting_for_reply_method = State()
    waiting_for_reply_contact = State()