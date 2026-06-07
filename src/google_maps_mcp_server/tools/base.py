"""Base tool class for Google Maps MCP tools."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import googlemaps
import structlog
from mcp import types as mcp_types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Settings

logger = structlog.get_logger()


def build_gmaps_client(settings: Settings) -> googlemaps.Client:
    """Build the googlemaps client — OtoDock-relay-aware.

    Hosted (relay): point the client at the OtoDock relay and pass the per-user
    session token via the ``X-OtoDock-Relay-Token`` header; the relay injects the
    real Google Maps key, meters the call, and proxies to Google. The googlemaps
    lib requires a non-empty key, so a placeholder is sent that the relay replaces.
    BYO: the configured key against Google's default endpoint.
    """
    if settings.relay_enabled:
        return googlemaps.Client(
            # Placeholder key — the relay replaces ?key= with the real one. Must
            # start with "AIza" to pass the googlemaps lib's key-format check.
            key="AIzaSyOtoDockRelayPlaceholderKey000000000000",
            base_url=settings.otodock_relay_base.rstrip("/") + "/google-maps",
            timeout=30,
            requests_kwargs={
                "headers": {"X-OtoDock-Relay-Token": settings.otodock_relay_token},
            },
        )
    return googlemaps.Client(key=settings.google_maps_api_key, timeout=30)


class BaseTool(ABC):
    """Base class for all Google Maps tools."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.gmaps = build_gmaps_client(settings)

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for MCP protocol."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for MCP protocol."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema for tool inputs."""
        pass

    def to_mcp_tool(self) -> mcp_types.Tool:
        """Convert to MCP Tool type."""
        return mcp_types.Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((googlemaps.exceptions.TransportError,)),
    )
    async def _execute_with_retry(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute Google Maps API call with retry logic."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool with given arguments."""
        pass

    def _format_response(
        self, data: Any, status: str = "success", error: str | None = None
    ) -> dict[str, Any]:
        """Format tool response consistently."""
        response = {
            "status": status,
            "tool": self.name,
        }

        if error:
            response["error"] = error
        else:
            response["data"] = data

        return response
