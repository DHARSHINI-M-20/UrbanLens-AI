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
    aws_region: str = "ap-south-1"
    bedrock_inference_profile: str = "apac.amazon.nova-lite-v1:0"
    local_detector_cost_per_invocation: float | None = None
    ocr_cost_per_invocation: float | None = None
    nova_lite_cost_per_invocation: float | None = None
    tesseract_cmd: str | None = None

    @staticmethod
    def _optional_price(variable: str) -> float | None:
        value = os.getenv(variable)
        if value is None or not value.strip():
            return None
        try:
            price = float(value)
        except ValueError as exc:
            raise ValueError(f"{variable} must be a non-negative number.") from exc
        if price < 0:
            raise ValueError(f"{variable} must be a non-negative number.")
        return price


@lru_cache
def get_settings() -> Settings:
    """Return cached settings populated from the environment."""
    return Settings(
        mongodb_uri=os.getenv("MONGODB_URI"),
        mongodb_database=os.getenv("MONGODB_DATABASE", "urbanlens"),
        google_maps_api_key=os.getenv("GOOGLE_MAPS_API_KEY"),
        aws_region=os.getenv("AWS_REGION", "ap-south-1"),
        bedrock_inference_profile=os.getenv("BEDROCK_INFERENCE_PROFILE", "apac.amazon.nova-lite-v1:0"),
        local_detector_cost_per_invocation=Settings._optional_price("LOCAL_DETECTOR_COST_PER_INVOCATION"),
        ocr_cost_per_invocation=Settings._optional_price("OCR_COST_PER_INVOCATION"),
        nova_lite_cost_per_invocation=Settings._optional_price("NOVA_LITE_COST_PER_INVOCATION"),
        tesseract_cmd=os.getenv("TESSERACT_CMD") or None,
    )
