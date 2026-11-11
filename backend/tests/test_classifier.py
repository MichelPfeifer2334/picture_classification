from app.services.classifier.ollama_classifier import build_schema


def test_schema_restricts_categories() -> None:
    schema = build_schema(["strand", "sonstiges"])
    assert schema["properties"]["category"]["enum"] == ["strand", "sonstiges"]
    assert set(schema["required"]) == {"category", "quality", "quality_reason", "caption"}
