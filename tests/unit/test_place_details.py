"""Unit tests for PlaceDetailsTool (OtoDock fork — Places Details via ``gmaps.place``).

The fork moved ``get_place_details`` onto the ``googlemaps`` library's Details
endpoint (``gmaps.place``), dropping the separate gapic client. These tests cover
that implementation.
"""

from unittest.mock import MagicMock

import googlemaps
import pytest

from google_maps_mcp_server.config import Settings
from google_maps_mcp_server.tools.places import PlaceDetailsTool


@pytest.mark.asyncio
async def test_place_details_tool_name(mock_settings: Settings) -> None:
    """Test place details tool name."""
    tool = PlaceDetailsTool(mock_settings)
    assert tool.name == "get_place_details"
    assert tool.description is not None
    assert tool.input_schema is not None


@pytest.mark.asyncio
async def test_place_details_execution(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """A Details result is mapped to the tool's place shape."""
    mock_gmaps_client.place.return_value = {
        "result": {
            "name": "Test Place",
            "formatted_address": "123 Test St",
            "geometry": {"location": {"lat": 1.0, "lng": 1.0}},
            "place_id": "pid1",
            "formatted_phone_number": "555-1234",
            "website": "http://test.com",
            "rating": 4.2,
        }
    }
    tool = PlaceDetailsTool(mock_settings)

    result = await tool.execute({"place_id": "pid1"})

    assert result["status"] == "success"
    data = result["data"]
    assert data["name"] == "Test Place"
    assert data["address"] == "123 Test St"
    assert data["location"] == {"lat": 1.0, "lng": 1.0}
    assert data["phone_number"] == "555-1234"
    assert data["website"] == "http://test.com"
    assert data["place_id"] == "pid1"


@pytest.mark.asyncio
async def test_place_details_opening_hours(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """Opening hours, when present, are flattened into the response."""
    mock_gmaps_client.place.return_value = {
        "result": {
            "name": "Cafe",
            "opening_hours": {"open_now": True, "weekday_text": ["Mon: 9-5"]},
        }
    }
    tool = PlaceDetailsTool(mock_settings)

    result = await tool.execute({"place_id": "pid1"})

    assert result["data"]["opening_hours"] == {
        "open_now": True,
        "weekday_text": ["Mon: 9-5"],
    }


@pytest.mark.asyncio
async def test_place_details_custom_fields_mapped(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """Friendly field names are mapped to the ``googlemaps`` lib's field names."""
    mock_gmaps_client.place.return_value = {"result": {"name": "Test Place"}}
    tool = PlaceDetailsTool(mock_settings)

    await tool.execute({"place_id": "pid1", "fields": ["name", "phone"]})

    fields = mock_gmaps_client.place.call_args.kwargs["fields"]
    assert "name" in fields
    assert "formatted_phone_number" in fields  # "phone" → lib name


@pytest.mark.asyncio
async def test_place_details_api_error(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """``googlemaps.exceptions.ApiError`` is caught and returned as an error response."""
    mock_gmaps_client.place.side_effect = googlemaps.exceptions.ApiError("NOT_FOUND")
    tool = PlaceDetailsTool(mock_settings)

    result = await tool.execute({"place_id": "pid1"})

    assert result["status"] == "error"
    assert "NOT_FOUND" in result["error"]
    assert result["tool"] == "get_place_details"
