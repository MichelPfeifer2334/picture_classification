import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class OllamaStatus(BaseModel):
    reachable: bool
    model: str
    model_available: bool


class HealthResponse(BaseModel):
    status: str
    ollama: OllamaStatus


class AppConfig(BaseModel):
    model: str
    categories: list[str]


@router.get("/config", response_model=AppConfig)
def config() -> AppConfig:
    """Konfiguration, die das Frontend braucht (Kategorienreihenfolge, Modellname)."""
    settings = get_settings()
    return AppConfig(model=settings.ollama_model, categories=settings.categories)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Prüft, ob das Backend läuft und ob Ollama inkl. konfiguriertem Modell erreichbar ist."""
    settings = get_settings()
    reachable = False
    model_available = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            resp.raise_for_status()
            reachable = True
            names = {m["name"] for m in resp.json().get("models", [])}
            model_available = settings.ollama_model in names
    except httpx.HTTPError:
        pass

    return HealthResponse(
        status="ok",
        ollama=OllamaStatus(
            reachable=reachable, model=settings.ollama_model, model_available=model_available
        ),
    )
