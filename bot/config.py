from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    bot_token: str
    bot_link: str = "https://t.me/your_bot_username"
    admin_chat_id: int = 0

    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    redis_url: str = "redis://localhost:6379/0"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    staff_email: str = ""

    huggingface_api_token: str = ""
    hf_image_model: str = "black-forest-labs/FLUX.1-schnell"
    hf_image_cache_dir: str = "generated_images"
    hf_provider: str = "hf-inference"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()