"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic import BaseModel


# Prefer a project-root .env file. backend/.env is also supported.
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")


class Settings(BaseModel):
    """Runtime settings for the API."""

    app_name: str = "UrbanLens AI"
    mongodb_uri: str | None = None
    mongodb_database: str = "urbanlens"
    google_maps_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return cached settings populated from the environment."""
    return Settings(
        mongodb_uri=os.getenv("MONGODB_URI"),
        mongodb_database=os.getenv("MONGODB_DATABASE", "urbanlens"),
        google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY"),
    )
