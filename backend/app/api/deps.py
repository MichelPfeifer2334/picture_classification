"""Gemeinsame Abhängigkeiten (Singletons). In Tests per app.dependency_overrides austauschbar."""

from functools import lru_cache

from app.core.config import get_settings
from app.services.classifier.ollama_classifier import OllamaClassifier
from app.services.jobs import ClassificationRunner
from app.services.storage import AlbumStore


@lru_cache
def get_store() -> AlbumStore:
    return AlbumStore(get_settings().data_dir)


@lru_cache
def get_runner() -> ClassificationRunner:
    s = get_settings()
    classifier = OllamaClassifier(
        host=s.ollama_host,
        model=s.ollama_model,
        categories=s.categories,
        timeout_s=s.ollama_timeout_s,
    )
    return ClassificationRunner(get_store(), classifier)
