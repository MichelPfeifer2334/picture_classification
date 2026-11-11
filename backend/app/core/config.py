from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Zentrale Konfiguration – Werte kommen aus Umgebungsvariablen bzw. backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Fotobuch Backend"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5vl:7b"
    ollama_timeout_s: float = 180.0

    # Ablage für Alben, Bilder und Exporte (relativ zum Startordner backend/)
    data_dir: Path = Path("../data")

    # Feste Kategorienliste – das Modell darf nur hieraus wählen
    categories: list[str] = [
        "strand",
        "landschaft",
        "stadt",
        "essen",
        "personen",
        "tiere",
        "sonstiges",
    ]

    # Bildgrößen (längste Kante in Pixeln)
    model_input_max_px: int = 1024
    thumb_max_px: int = 400

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
