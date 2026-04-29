import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]

QUESTIONS_PATH = ROOT_DIR / "data" / "questions.json"
ANIMALS_PATH = ROOT_DIR / "data" / "animals.json"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"
GITIGNORE_PATH = ROOT_DIR / ".gitignore"
REQUIREMENTS_PATH = ROOT_DIR / "requirements.txt"
MIGRATION_PATH = ROOT_DIR / "migrations" / "001_init.sql"

REQUIRED_ENV_KEYS = {
    "BOT_TOKEN",
    "BOT_LINK",
    "ADMIN_CHAT_ID",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "REDIS_URL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "STAFF_EMAIL",
    "HUGGINGFACE_API_TOKEN",
    "HF_IMAGE_MODEL",
    "HF_IMAGE_CACHE_DIR",
    "HF_PROVIDER",
}

REQUIRED_GITIGNORE_PATTERNS = {
    ".env",
    ".venv/",
    "venv/",
    "__pycache__/",
    "*.pyc",
    ".idea/",
    "generated_images/",
}

REQUIRED_REQUIREMENTS = {
    "aiogram",
    "pydantic-settings",
    "python-dotenv",
    "asyncpg",
    "redis",
    "huggingface_hub",
    "Pillow",
}

FORBIDDEN_ANIMAL_WORDS = {
    "panda",
    "панда",
    "панды",
    "большая панда",
}


class CheckResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def ok(self, message: str) -> None:
        print(f"✅ {message}")

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("ИТОГ ПРОВЕРКИ")
        print("=" * 60)

        if self.errors:
            print("\n❌ Ошибки:")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print("\n⚠️ Предупреждения:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ Всё хорошо. Критичных проблем не найдено.")
        elif not self.errors:
            print("\n✅ Критичных ошибок нет, но есть предупреждения.")
        else:
            print("\n❌ Есть ошибки, лучше исправить перед сдачей.")


def load_json_file(path: Path, result: CheckResult) -> Any | None:
    if not path.exists():
        result.fail(f"Файл не найден: {path.relative_to(ROOT_DIR)}")
        return None

    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        result.fail(f"Некорректный JSON в {path.relative_to(ROOT_DIR)}: {exc}")
        return None


def contains_forbidden_animal(text: str) -> bool:
    normalized = text.lower()
    return any(word in normalized for word in FORBIDDEN_ANIMAL_WORDS)


def check_animals(animals: Any, result: CheckResult) -> set[str]:
    if not isinstance(animals, list):
        result.fail("animals.json должен содержать список животных")
        return set()

    animal_ids: set[str] = set()

    for index, animal in enumerate(animals):
        if not isinstance(animal, dict):
            result.fail(f"animals.json: элемент #{index + 1} должен быть объектом")
            continue

        animal_id = animal.get("id")
        name = animal.get("name")
        image_path = animal.get("image_path")
        description = animal.get("description")

        if not animal_id:
            result.fail(f"animals.json: у животного #{index + 1} нет поля id")
            continue

        if animal_id in animal_ids:
            result.fail(f"animals.json: дублирующийся id животного: {animal_id}")

        animal_ids.add(animal_id)

        if not name:
            result.fail(f"animals.json: у животного {animal_id} нет name")

        if not image_path:
            result.fail(f"animals.json: у животного {animal_id} нет image_path")
        else:
            full_image_path = ROOT_DIR / image_path
            if not full_image_path.exists():
                result.fail(
                    f"animals.json: картинка для {animal_id} не найдена: {image_path}"
                )

        if not description:
            result.fail(f"animals.json: у животного {animal_id} нет description")
        elif len(description.strip()) < 50:
            result.warn(
                f"animals.json: описание животного {animal_id} выглядит слишком коротким"
            )

        joined_text = " ".join(
            str(value)
            for value in [animal_id, name, image_path, description]
            if value is not None
        )
        if contains_forbidden_animal(joined_text):
            result.fail(
                f"animals.json: найдено запрещённое упоминание панды у {animal_id}"
            )

    if len(animal_ids) < 4:
        result.warn("animals.json: животных меньше 4, викторина может выглядеть бедно")

    result.ok(f"animals.json проверен, животных: {len(animal_ids)}")
    return animal_ids


def check_questions(
    questions: Any,
    animal_ids: set[str],
    result: CheckResult,
) -> None:
    if not isinstance(questions, list):
        result.fail("questions.json должен содержать список вопросов")
        return

    question_ids: set[str] = set()
    scored_animals: dict[str, int] = {animal_id: 0 for animal_id in animal_ids}

    for question_index, question in enumerate(questions):
        if not isinstance(question, dict):
            result.fail(f"questions.json: вопрос #{question_index + 1} должен быть объектом")
            continue

        question_id = question.get("id")
        question_text = question.get("text")
        options = question.get("options")

        if not question_id:
            result.fail(f"questions.json: у вопроса #{question_index + 1} нет id")
        elif question_id in question_ids:
            result.fail(f"questions.json: дублирующийся id вопроса: {question_id}")
        else:
            question_ids.add(question_id)

        if not question_text:
            result.fail(f"questions.json: у вопроса {question_id} нет text")
        elif contains_forbidden_animal(question_text):
            result.fail(f"questions.json: вопрос {question_id} содержит упоминание панды")

        if not isinstance(options, list) or len(options) < 2:
            result.fail(
                f"questions.json: вопрос {question_id} должен иметь минимум 2 варианта"
            )
            continue

        for option_index, option in enumerate(options):
            if not isinstance(option, dict):
                result.fail(
                    f"questions.json: вариант #{option_index + 1} вопроса {question_id} "
                    "должен быть объектом"
                )
                continue

            option_text = option.get("text")
            scores = option.get("scores")
            image_tags = option.get("image_tags")

            if not option_text:
                result.fail(
                    f"questions.json: у варианта #{option_index + 1} вопроса "
                    f"{question_id} нет text"
                )
            elif contains_forbidden_animal(option_text):
                result.fail(
                    f"questions.json: вариант #{option_index + 1} вопроса "
                    f"{question_id} содержит упоминание панды"
                )

            if not isinstance(scores, dict) or not scores:
                result.fail(
                    f"questions.json: у варианта #{option_index + 1} вопроса "
                    f"{question_id} нет scores"
                )
            else:
                for animal_id, points in scores.items():
                    if animal_id not in animal_ids:
                        result.fail(
                            f"questions.json: вариант #{option_index + 1} вопроса "
                            f"{question_id} ссылается на неизвестное животное: {animal_id}"
                        )

                    if not isinstance(points, int) or points <= 0:
                        result.fail(
                            f"questions.json: score для {animal_id} в вопросе "
                            f"{question_id} должен быть положительным целым числом"
                        )

                    if animal_id in scored_animals and isinstance(points, int):
                        scored_animals[animal_id] += points

            if not isinstance(image_tags, list) or not image_tags:
                result.fail(
                    f"questions.json: у варианта #{option_index + 1} вопроса "
                    f"{question_id} нет непустого image_tags"
                )
            else:
                for tag in image_tags:
                    if not isinstance(tag, str) or not tag.strip():
                        result.fail(
                            f"questions.json: некорректный image_tag в вопросе {question_id}"
                        )

    unreachable_animals = [
        animal_id
        for animal_id, total_score in scored_animals.items()
        if total_score <= 0
    ]

    if unreachable_animals:
        result.fail(
            "Некоторые животные невозможно получить по результатам викторины: "
            + ", ".join(unreachable_animals)
        )

    result.ok(f"questions.json проверен, вопросов: {len(question_ids)}")

    print("\nБаллы по животным в questions.json:")
    for animal_id, total_score in sorted(scored_animals.items()):
        print(f"  - {animal_id}: {total_score}")


def parse_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}

    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def looks_like_real_secret(key: str, value: str) -> bool:
    if not value:
        return False

    safe_words = {
        "your",
        "example",
        "localhost",
        "changeme",
        "change_me",
        "placeholder",
        "0",
    }

    lowered = value.lower()

    if any(word in lowered for word in safe_words):
        return False

    if key in {"BOT_TOKEN", "HUGGINGFACE_API_TOKEN", "SMTP_PASSWORD", "DB_PASSWORD"}:
        return len(value) > 12

    if "PASSWORD" in key or "TOKEN" in key or "SECRET" in key:
        return len(value) > 12

    return False


def check_env_example(result: CheckResult) -> None:
    if not ENV_EXAMPLE_PATH.exists():
        result.fail(".env.example не найден")
        return

    values = parse_env_example(ENV_EXAMPLE_PATH)
    missing_keys = sorted(REQUIRED_ENV_KEYS - set(values))

    if missing_keys:
        result.fail(
            ".env.example: отсутствуют переменные: " + ", ".join(missing_keys)
        )

    for key, value in values.items():
        if looks_like_real_secret(key, value):
            result.fail(
                f".env.example: значение {key} похоже на реальный секрет, "
                "лучше заменить на placeholder"
            )

    result.ok(".env.example проверен")


def check_gitignore(result: CheckResult) -> None:
    if not GITIGNORE_PATH.exists():
        result.fail(".gitignore не найден")
        return

    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    lines = {
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    missing_patterns = sorted(REQUIRED_GITIGNORE_PATTERNS - lines)

    if missing_patterns:
        result.warn(
            ".gitignore: желательно добавить: " + ", ".join(missing_patterns)
        )

    result.ok(".gitignore проверен")


def check_env_not_tracked(result: CheckResult) -> None:
    try:
        completed = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        result.warn("Git не найден в PATH, не удалось проверить tracked .env")
        return

    if completed.stdout.strip():
        result.fail(".env отслеживается Git — его нельзя коммитить в репозиторий")
    else:
        result.ok(".env не отслеживается Git")


def check_requirements(result: CheckResult) -> None:
    if not REQUIREMENTS_PATH.exists():
        result.fail("requirements.txt не найден")
        return

    content = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    normalized = content.lower()

    missing = [
        dependency
        for dependency in REQUIRED_REQUIREMENTS
        if dependency.lower() not in normalized
    ]

    if missing:
        result.fail("requirements.txt: отсутствуют зависимости: " + ", ".join(missing))

    result.ok("requirements.txt проверен")


def check_migration(result: CheckResult) -> None:
    if not MIGRATION_PATH.exists():
        result.fail("migrations/001_init.sql не найден")
        return

    content = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    required_fragments = [
        "create table",
        "quiz_results",
        "contact_requests",
        "feedback",
        "scores",
        "jsonb",
        "image_tags",
    ]

    for fragment in required_fragments:
        if fragment not in content:
            result.fail(f"001_init.sql: не найден обязательный фрагмент: {fragment}")

    result.ok("migrations/001_init.sql проверен")


def main() -> int:
    result = CheckResult()

    print("Проверка проекта PythonZoo\n")

    animals = load_json_file(ANIMALS_PATH, result)
    questions = load_json_file(QUESTIONS_PATH, result)

    animal_ids: set[str] = set()

    if animals is not None:
        animal_ids = check_animals(animals, result)

    if questions is not None:
        check_questions(questions, animal_ids, result)

    check_env_example(result)
    check_gitignore(result)
    check_env_not_tracked(result)
    check_requirements(result)
    check_migration(result)

    result.print_summary()

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())