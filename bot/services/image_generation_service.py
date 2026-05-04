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


def build_result_prompt(animal: dict[str, Any], image_tags: list[str]) -> str:
    animal_id = animal["id"]
    base_prompt = ANIMAL_BASE_PROMPTS.get(
        animal_id,
        f"Create a warm semi-realistic digital illustration of {animal['name']} "
        "from Moscow Zoo.",
    )

    unique_tags: list[str] = []

    # Keep only the first occurrence of each tag.
    # This makes the prompt stable and avoids overloading it with repeated cues.
    for tag in image_tags:
        if tag not in unique_tags:
            unique_tags.append(tag)

    # Limit visual cues so the model keeps the animal as the main subject.
    tags_text = ", ".join(unique_tags[:12])

    if tags_text:
        extra_part = f"Additional visual cues: {tags_text}. "
    else:
        extra_part = ""

    return (
        f"{base_prompt} "
        f"{extra_part}"
        "Style: high-quality semi-realistic illustration, soft natural lighting, "
        "friendly mood, rich details, visually appealing for a Telegram bot. "
        "Show one main animal clearly. "
        "No text, no captions, no watermark, no frame."
    )


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
) -> str | None:
    if not settings.huggingface_api_token:
        logger.warning("HUGGINGFACE_API_TOKEN is not configured")
        return None

    prompt = build_result_prompt(animal, image_tags)
    prompt_hash = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:16]

    cache_dir = Path(settings.hf_image_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    output_path = cache_dir / f"{animal['id']}_{prompt_hash}.png"

    # Cache by prompt hash: identical quiz results should not call
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