"""App settings, read from environment variables or a .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://vnaana:vnaana@localhost:5432/vnaana"
    sql_echo: bool = False
    ai_provider: Literal["ollama", "fontys"] = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: int = 90
    fontys_api_key: SecretStr | None = None
    fontys_model: str = "fontys-gpt-5.6-sol"
    fontys_endpoint: str = "https://api.portkey.ai/v1/chat/completions"
    fontys_timeout_seconds: float = 90

    genre_classification_model_path: Path | None = None
    genre_classification_device: str = "cpu"
    genre_classification_pipeline_enabled: bool = False

    supabase_url: str | None = None
    supabase_publishable_key: str | None = None

    # Read from GOOGLE_TRANSLATE_API_KEY. Server-side only, never send it to the frontend.
    google_translate_api_key: str | None = None
    google_translate_timeout_seconds: float = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
