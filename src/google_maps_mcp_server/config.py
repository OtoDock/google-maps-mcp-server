"""Configuration management with validation."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Google Maps MCP Server configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    google_maps_api_key: str = ""
    version: str = "0.3.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    max_results: int = 20
    default_radius_meters: int = 5000
    max_radius_meters: int = 50000
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 10.0

    @model_validator(mode="after")
    def _check_credentials(self) -> Settings:
        """Require a Google Maps API key (bring-your-own-key)."""
        if not self.google_maps_api_key.strip():
            raise ValueError("Set GOOGLE_MAPS_API_KEY.")
        return self
