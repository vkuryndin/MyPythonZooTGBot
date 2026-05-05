import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Any

from huggingface_hub import InferenceClient

from bot.config import settings


logger = logging.getLogger(__name__)

AI_GENERATION_SEMAPHORE = asyncio.Semaphore(2)

MAX_UNIQUE_IMAGE_TAGS = 15
MAX_VISIBLE_SECONDARY_ANIMALS = 1
MAX_SECONDARY_STYLE_INFLUENCES = 1

ANIMAL_BASE_PROMPTS = {
    "manul": (
        "Create a warm semi-realistic digital illustration of a Pallas's cat "
        "from Moscow Zoo. The animal should look fluffy, calm, observant, "
        "slightly serious and very charming."
    ),
    "meerkat": (
        "Create a warm semi-realistic digital illustration of a meerkat "
        "from Moscow Zoo. The animal should look alert, social, friendly "
        "and energetic."
    ),
    "elephant": (
        "Create a warm semi-realistic digital illustration of an elephant "
        "from Moscow Zoo. The animal should look calm, wise, kind, reliable "
        "and majestic."
    ),
    "tiger": (
        "Create a warm semi-realistic digital illustration of a tiger "
        "from Moscow Zoo. The animal should look strong, focused, graceful "
        "and confident."
    ),
    "flamingo": (
        "Create a warm semi-realistic digital illustration of a flamingo "
        "from Moscow Zoo. The animal should look elegant, bright, stylish "
        "and graceful."
    ),
    "otter": (
        "Create a warm semi-realistic digital illustration of an otter "
        "from Moscow Zoo. The animal should look playful, joyful, active "
        "and curious."
    ),
    "sloth": (
        "Create a warm semi-realistic digital illustration of a sloth "
        "from Moscow Zoo. The animal should look relaxed, cozy, soft "
        "and peaceful."
    ),
    "sea_lion": (
        "Create a warm semi-realistic digital illustration of a sea lion "
        "from Moscow Zoo. The animal should look charismatic, expressive, "
        "playful and energetic."
    ),
}

ANIMAL_PROMPT_SUBJECTS = {
    "manul": "the Pallas's cat",
    "meerkat": "the meerkat",
    "elephant": "the elephant",
    "tiger": "the tiger",
    "flamingo": "the flamingo",
    "otter": "the otter",
    "sloth": "the sloth",
    "sea_lion": "the sea lion",
}

ANIMAL_SECONDARY_VISUAL_TRAITS = {
    "manul": [
        "observant quiet mood",
        "reserved stillness",
        "cozy sheltered atmosphere",
    ],
    "otter": [
        "playful lively energy",
        "curious expression",
        "waterfront activity",
    ],
    "sloth": [
        "relaxed calm mood",
        "soft unhurried posture",
        "gentle cozy atmosphere",
    ],
    "tiger": [
        "focused intensity",
        "confident strong presence",
        "powerful dynamic stance",
    ],
    "meerkat": [
        "alert social mood",
        "group-oriented composition",
        "active attentive pose",
    ],
    "elephant": [
        "grounded stable mood",
        "calm reliable presence",
        "spacious balanced composition",
    ],
    "flamingo": [
        "elegant bright presentation",
        "graceful composition",
        "festive colorful accent",
    ],
    "sea_lion": [
        "bold expressive energy",
        "confident open posture",
        "dynamic outdoor feeling",
    ],
}


def get_secondary_animals(
    scores: dict[str, int] | None,
    winner_id: str,
    limit: int,
) -> list[str]:
    if not scores:
        return []

    filtered_scores: list[tuple[str, int]] = []

    for animal_id, score in scores.items():
        if animal_id == winner_id:
            continue

        try:
            numeric_score = int(score)
        except (TypeError, ValueError):
            continue

        filtered_scores.append((animal_id, numeric_score))

    filtered_scores.sort(key=lambda item: item[1], reverse=True)

    secondary_animals: list[str] = []

    for animal_id, score in filtered_scores:
        if score <= 0:
            continue

        secondary_animals.append(animal_id)

        if len(secondary_animals) >= limit:
            break

    return secondary_animals


def build_secondary_visual_direction(
    scores: dict[str, int] | None,
    winner_id: str,
    excluded_animal_ids: set[str] | None = None,
) -> str:
    excluded_ids = set(excluded_animal_ids or set())
    excluded_ids.add(winner_id)

    if not scores:
        return ""

    filtered_scores: list[tuple[str, int]] = []

    for animal_id, score in scores.items():
        if animal_id in excluded_ids:
            continue

        try:
            numeric_score = int(score)
        except (TypeError, ValueError):
            continue

        filtered_scores.append((animal_id, numeric_score))

    filtered_scores.sort(key=lambda item: item[1], reverse=True)

    selected_traits: list[str] = []

    for animal_id, score in filtered_scores:
        if score <= 0:
            continue

        traits = ANIMAL_SECONDARY_VISUAL_TRAITS.get(animal_id, [])

        if not traits:
            continue

        primary_trait = traits[0]

        if primary_trait not in selected_traits:
            selected_traits.append(primary_trait)

        if len(selected_traits) >= MAX_SECONDARY_STYLE_INFLUENCES:
            break

    return ", ".join(selected_traits)


def build_result_prompt(
    animal: dict[str, Any],
    image_tags: list[str],
    scores: dict[str, int] | None = None,
) -> str:
    animal_id = animal["id"]

    base_prompt = ANIMAL_BASE_PROMPTS.get(
        animal_id,
        "Create a warm semi-realistic digital illustration of an animal "
        "from Moscow Zoo.",
    )
    prompt_subject = ANIMAL_PROMPT_SUBJECTS.get(animal_id, "the animal")

    unique_tags: list[str] = []

    # Keep only the first occurrence of each tag.
    # This makes the prompt stable and avoids overloading it with repeated cues.
    for tag in image_tags:
        if tag not in unique_tags:
            unique_tags.append(tag)

    # Limit visual cues so the prompt stays rich but still coherent.
    selected_tags = unique_tags[:MAX_UNIQUE_IMAGE_TAGS]
    tags_text = ", ".join(selected_tags)

    visible_secondary_animals = get_secondary_animals(
        scores=scores,
        winner_id=animal_id,
        limit=MAX_VISIBLE_SECONDARY_ANIMALS,
    )
    visible_secondary_animal_id = (
        visible_secondary_animals[0] if visible_secondary_animals else None
    )
    visible_secondary_subject = (
        ANIMAL_PROMPT_SUBJECTS.get(visible_secondary_animal_id, "the secondary animal")
        if visible_secondary_animal_id
        else ""
    )

    secondary_visual_direction = build_secondary_visual_direction(
        scores=scores,
        winner_id=animal_id,
        excluded_animal_ids=(
            {visible_secondary_animal_id}
            if visible_secondary_animal_id is not None
            else set()
        ),
    )

    prompt_parts = [base_prompt]

    if visible_secondary_subject:
        # The quiz winner remains the main subject, but the second-place animal
        # should appear as a visible companion in the same scene.
        prompt_parts.append(
            f"Keep {prompt_subject} as the clear main animal in the image. "
            f"Also include {visible_secondary_subject} as a visible secondary "
            "supporting animal in the same scene. "
            "The main animal must remain dominant, and the secondary animal "
            "should be smaller or less prominent."
        )
    else:
        prompt_parts.append(
            f"Keep {prompt_subject} as the only main animal in the image."
        )

    if tags_text:
        prompt_parts.append(f"Personalized visual cues: {tags_text}.")

    if secondary_visual_direction:
        prompt_parts.append(
            "Additional score-based visual direction: "
            f"add {secondary_visual_direction}, without changing the animal species."
        )

    prompt_parts.append(
        "Style: high-quality semi-realistic illustration, realistic animal anatomy, "
        "natural proportions, soft natural lighting, friendly mood, rich details, "
        "visually appealing for a Telegram bot."
    )

    if visible_secondary_subject:
        prompt_parts.append(
            "Show at most two animals total: the main result animal as the clear subject "
            "and the second-place animal as a supporting presence. "
            "Do not merge species or create hybrid animals. "
            "No text, no captions, no watermark, no frame."
        )
    else:
        prompt_parts.append(
            "Show one main animal clearly. Do not mix species. "
            "No text, no captions, no watermark, no frame."
        )

    return " ".join(prompt_parts)


def _build_client() -> InferenceClient:
    return InferenceClient(
        provider=settings.hf_provider,
        api_key=settings.huggingface_api_token,
    )


def _generate_image_sync(
    prompt: str,
    model: str,
    output_path: Path,
) -> str | None:
    try:
        client = _build_client()

        image = client.text_to_image(
            prompt,
            model=model,
        )

        image.save(output_path)
        return str(output_path)

    except Exception:
        logger.exception("Failed to generate image via Hugging Face InferenceClient")
        return None


async def generate_result_image(
    animal: dict[str, Any],
    image_tags: list[str],
    scores: dict[str, int] | None = None,
) -> str | None:
    if not settings.huggingface_api_token:
        logger.warning("HUGGINGFACE_API_TOKEN is not configured")
        return None

    prompt = build_result_prompt(
        animal=animal,
        image_tags=image_tags,
        scores=scores or {},
    )

    # debugging AI prompts.
    print("\n===== AI PROMPT START =====")
    print(prompt)
    print("===== AI PROMPT END =====\n")

    prompt_hash = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:16]

    cache_dir = Path(settings.hf_image_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    output_path = cache_dir / f"{animal['id']}_{prompt_hash}.png"

    # Cache by prompt hash: identical prompt inputs should not call
    # the image generation API again.
    if output_path.exists():
        logger.info("Generated image cache hit for animal_id=%s", animal["id"])
        return str(output_path)

    logger.info("Starting image generation for animal_id=%s", animal["id"])
    started_at = time.perf_counter()

    # Limit concurrent image generations to avoid blocking the bot
    # and hitting provider limits.
    async with AI_GENERATION_SEMAPHORE:
        generated_path = await asyncio.to_thread(
            _generate_image_sync,
            prompt,
            settings.hf_image_model,
            output_path,
        )

    elapsed_seconds = time.perf_counter() - started_at

    if generated_path is None:
        logger.warning(
            "Image generation failed for animal_id=%s duration=%.2fs",
            animal["id"],
            elapsed_seconds,
        )
        return None

    logger.info(
        "Image generation completed for animal_id=%s duration=%.2fs",
        animal["id"],
        elapsed_seconds,
    )

    return generated_path