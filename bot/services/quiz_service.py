import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = BASE_DIR / "data" / "questions.json"
ANIMALS_PATH = BASE_DIR / "data" / "animals.json"


class QuizService:
    """Service for loading quiz data and calculating quiz results."""

    def __init__(self) -> None:
        self.questions = self._load_json(QUESTIONS_PATH)
        self.animals = self._load_json(ANIMALS_PATH)

    def get_questions(self) -> list[dict[str, Any]]:
        return self.questions

    def get_question(self, question_index: int) -> dict[str, Any]:
        return self.questions[question_index]

    def is_last_question(self, question_index: int) -> bool:
        return question_index >= len(self.questions) - 1

    def get_total_questions_count(self) -> int:
        return len(self.questions)

    def get_option_scores(
        self,
        question_index: int,
        option_index: int,
    ) -> dict[str, int]:
        question = self.get_question(question_index)
        return question["options"][option_index]["scores"]

    def get_result_animal(self, scores: dict[str, int]) -> dict[str, Any]:
        winner_id = max(scores, key=scores.get)
        return self._find_animal_by_id(winner_id)

    def get_animal_by_id(self, animal_id: str) -> dict[str, Any]:
        """Get animal by id."""

        return self._find_animal_by_id(animal_id)

    def _find_animal_by_id(self, animal_id: str) -> dict[str, Any]:
        for animal in self.animals:
            if animal["id"] == animal_id:
                return animal

        raise ValueError(f"Animal with id '{animal_id}' was not found")

    @staticmethod
    def _load_json(path: Path) -> list[dict[str, Any]]:
        with path.open(encoding="utf-8") as file:
            return json.load(file)

    def get_option_image_tags(self, question_index: int, option_index: int) -> list[str]:
        """Return image tags for selected option."""

        question = self.get_question(question_index)
        option = question["options"][option_index]
        return option.get("image_tags", [])

quiz_service = QuizService()