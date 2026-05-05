import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = BASE_DIR / "data" / "questions.json"
ANIMALS_PATH = BASE_DIR / "data" / "animals.json"


class QuizService:
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

    def get_result_animal(
        self,
        scores: dict[str, int],
        primary_hits: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        winner_id = self.get_result_animal_id(
            scores=scores,
            primary_hits=primary_hits,
        )
        return self._find_animal_by_id(winner_id)

    def get_result_animal_id(
        self,
        scores: dict[str, int],
        primary_hits: dict[str, int] | None = None,
    ) -> str:
        if not scores:
            raise ValueError("Scores must not be empty")

        max_score = max(scores.values())
        candidates = [
            animal_id
            for animal_id, score in scores.items()
            if score == max_score
        ]

        if len(candidates) == 1:
            return candidates[0]

        primary_hits = primary_hits or {}
        max_primary_hits = max(
            int(primary_hits.get(animal_id, 0))
            for animal_id in candidates
        )

        primary_candidates = [
            animal_id
            for animal_id in candidates
            if int(primary_hits.get(animal_id, 0)) == max_primary_hits
        ]

        if len(primary_candidates) == 1:
            return primary_candidates[0]

        return self._get_stable_tie_break_winner(primary_candidates)

    def _get_stable_tie_break_winner(self, candidates: list[str]) -> str:
        candidate_set = set(candidates)

        for animal in self.animals:
            animal_id = animal["id"]

            if animal_id in candidate_set:
                return animal_id

        return candidates[0]

    def get_animal_by_id(self, animal_id: str) -> dict[str, Any]:
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
        question = self.get_question(question_index)
        option = question["options"][option_index]
        return option.get("image_tags", [])


quiz_service = QuizService()