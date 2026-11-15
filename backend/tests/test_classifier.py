from app.models.album import Classification
from app.services.classifier.ollama_classifier import build_schema


def test_schema_restricts_categories_and_requires_all() -> None:
    schema = build_schema(["strand", "sonstiges"])
    assert schema["properties"]["category"]["enum"] == ["strand", "sonstiges"]
    assert set(schema["required"]) == set(Classification.model_fields)


def test_classification_is_lenient() -> None:
    c = Classification.model_validate(
        {"category": "strand", "aesthetic_score": 12, "issues": ["blurry", "quatsch"]}
    )
    assert c.aesthetic_score == 10
    assert c.issues == ["blurry"]


def test_old_album_json_still_loads() -> None:
    """Alte Klassifizierungen (quality/quality_reason) dürfen das Laden nicht brechen."""
    c = Classification.model_validate(
        {"category": "strand", "quality": "good", "quality_reason": "x", "caption": "y"}
    )
    assert c.aesthetic_score == 5
