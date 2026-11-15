from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Zentrale Konfiguration – Werte kommen aus Umgebungsvariablen bzw. backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Fotobuch Backend"

    # --- Ollama ---------------------------------------------------------------
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5vl:7b"
    ollama_timeout_s: float = 180.0

    # Ablage für Alben, Bilder und Exporte (relativ zum Startordner backend/)
    data_dir: Path = Path("../data")

    # Feste Kategorienliste – das Modell darf nur hieraus wählen (letzte = Fallback)
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
    thumb_max_px: int = 480

    # --- Auswahl (siehe docs/04-modell.md) ------------------------------------
    default_min_score: float = 6.0  # Mindest-Score fürs Fotobuch (Regler "Strenge")
    dup_hamming: int = 8  # pHash-Abstand, ab dem Bilder als (fast) identisch gelten
    burst_hamming: int = 20  # lockerer Abstand für Serienbilder …
    burst_seconds: float = 4.0  # … wenn sie innerhalb dieser Zeit aufgenommen wurden
    blur_abs: float = 15.0  # Schärfe unter diesem Wert = unscharf
    blur_rel: float = 0.25  # … oder unter diesem Anteil des Album-Medians
    scene_minutes: float = 30.0  # gleiches Motiv innerhalb dieser Zeit = "ähnliches Motiv"
    similar_keep: int = 2  # max. Bilder pro Gruppe mit ähnlichem Motiv …
    similar_keep_margin: float = 0.5  # … wenn das zweite fast so gut ist wie das beste

    # --- Mini-Kapitel ---------------------------------------------------------
    chapter_gap_minutes: float = 90.0  # Zeitlücke, ab der ein neues Kapitel beginnt
    chapter_max_images: int = 30  # längere Kapitel werden an der größten Lücke geteilt
    chapter_min_images: int = 3  # weniger Bilder im Buch → keine eigene Überschrift
    title_band_mm: float = 16.0  # Platz für die Kapitelüberschrift auf der ersten Seite

    # --- Fotobuch-Layout (siehe docs/06-pdf-fotobuch.md) ----------------------
    page_width_mm: float = 297.0  # Endformat (A4 quer)
    page_height_mm: float = 210.0
    bleed_mm: float = 3.0  # Beschnittzugabe je Seite
    margin_mm: float = 12.0  # Rand zum Seitenende
    gutter_mm: float = 4.0  # Abstand zwischen Bildern
    print_dpi: int = 300  # Zielauflösung der eingebetteten Bilder
    hero_min_score: float = 8.5  # ab diesem Score: randlose Ganzseite (nur Querformat)

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
