"""Google Maps MCP Server - Production-ready MCP server for Google Maps Platform APIs."""

from .config import Settings
from .server import GoogleMapsMCPServer, main

__version__ = "0.3.2"
__all__ = ["GoogleMapsMCPServer", "Settings", "main"]
