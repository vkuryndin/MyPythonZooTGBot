from typing import Any


last_results: dict[int, dict[str, Any]] = {}


def save_last_result(user_id: int, animal: dict[str, Any]) -> None:
    """Save user's last quiz result in memory."""

    last_results[user_id] = animal


def get_last_result(user_id: int) -> dict[str, Any] | None:
    """Get user's last quiz result from memory."""

    return last_results.get(user_id)