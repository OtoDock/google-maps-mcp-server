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
    # OtoDock relay (hosted mode): when both are set the server routes Google Maps
    # calls through the OtoDock relay (which holds the real key, meters usage, and
    # proxies to Google) instead of using google_maps_api_key directly. Injected by
    # the OtoDock platform; harmless/unused for standalone (BYO-key) use.
    otodock_relay_base: str = ""
    otodock_relay_token: str = ""
    otodock_relay_error: str = ""
    version: str = "0.2.2"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    max_results: int = 20
    default_radius_meters: int = 5000
    max_radius_meters: int = 50000
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 10.0

    @property
    def relay_enabled(self) -> bool:
        """True when running via the OtoDock relay (hosted mode)."""
        return bool(self.otodock_relay_base and self.otodock_relay_token)

    @model_validator(mode="after")
    def _check_credentials(self) -> "Settings":
        """Require either a Google Maps API key (BYO) or the OtoDock relay (hosted)."""
        if not (self.google_maps_api_key.strip() or self.relay_enabled):
            raise ValueError(
                "Set GOOGLE_MAPS_API_KEY, or run via the OtoDock relay "
                "(OTODOCK_RELAY_BASE + OTODOCK_RELAY_TOKEN)."
            )
        return self
