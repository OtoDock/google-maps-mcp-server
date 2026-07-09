"""Unit tests for the Places tool (OtoDock fork — Places API **Text Search**).

The fork reimplemented ``search_places`` on the ``googlemaps`` library's Text
Search (``gmaps.places``), replacing upstream's Nearby Search + client-side
substring keyword filter (which dropped valid multi-word matches like "gas
station"). These tests cover that implementation.
"""

from unittest.mock import MagicMock

import googlemaps
import pytest

from google_maps_mcp_server.config import Settings
from google_maps_mcp_server.tools.places import PlacesTool


@pytest.mark.asyncio
async def test_places_tool_name() -> None:
    """Test places tool name."""
    settings = Settings(google_maps_api_key="AIzaSyDEMO_KEY_12345678901234567890123")
    tool = PlacesTool(settings)
    assert tool.name == "search_places"


@pytest.mark.asyncio
async def test_places_tool_schema() -> None:
    """Test places tool has valid schema."""
    settings = Settings(google_maps_api_key="AIzaSyDEMO_KEY_12345678901234567890123")
    tool = PlacesTool(settings)
    schema = tool.input_schema

    assert schema["type"] == "object"
    assert "location" in schema["properties"]
    assert "keyword" in schema["properties"]
    assert schema["required"] == ["location", "keyword"]


@pytest.mark.asyncio
async def test_places_tool_mcp_conversion() -> None:
    """Test places tool converts to MCP Tool type."""
    settings = Settings(google_maps_api_key="AIzaSyDEMO_KEY_12345678901234567890123")
    tool = PlacesTool(settings)
    mcp_tool = tool.to_mcp_tool()

    assert mcp_tool.name == "search_places"
    assert mcp_tool.description is not None
    assert mcp_tool.inputSchema is not None


@pytest.mark.asyncio
async def test_places_execute_text_search(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """A Text Search result is mapped to the tool's place shape."""
    mock_gmaps_client.places.return_value = {
        "results": [
            {
                "name": "Test Restaurant",
                "formatted_address": "123 Main St",
                "geometry": {"location": {"lat": 40.7128, "lng": -74.0060}},
                "rating": 4.5,
                "types": ["restaurant"],
                "place_id": "test_place_id",
            }
        ]
    }
    tool = PlacesTool(mock_settings)

    result = await tool.execute({"location": "40.7128,-74.0060", "keyword": "restaurant"})

    assert result["status"] == "success"
    assert result["data"]["count"] == 1
    place = result["data"]["places"][0]
    assert place["name"] == "Test Restaurant"
    assert place["address"] == "123 Main St"
    assert place["location"] == {"lat": 40.7128, "lng": -74.0060}
    assert place["rating"] == 4.5
    assert place["types"] == ["restaurant"]
    assert place["place_id"] == "test_place_id"


@pytest.mark.asyncio
async def test_places_calls_text_search_with_params(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """The tool forwards keyword/location/radius/type to ``gmaps.places`` (Text Search)."""
    mock_gmaps_client.places.return_value = {"results": []}
    tool = PlacesTool(mock_settings)

    await tool.execute(
        {
            "location": "37.7749,-122.4194",
            "keyword": "restaurant",
            "radius": 2000,
            "type": "restaurant",
        }
    )

    mock_gmaps_client.places.assert_called_once()
    kwargs = mock_gmaps_client.places.call_args.kwargs
    assert kwargs["query"] == "restaurant"
    assert kwargs["location"] == (37.7749, -122.4194)
    assert kwargs["radius"] == 2000
    assert kwargs["type"] == "restaurant"


@pytest.mark.asyncio
async def test_places_radius_clamped_to_max(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """Radius above ``max_radius_meters`` is clamped before the Text Search call."""
    mock_gmaps_client.places.return_value = {"results": []}
    tool = PlacesTool(mock_settings)

    await tool.execute({"location": "1.0,2.0", "keyword": "park", "radius": 999_999})

    assert mock_gmaps_client.places.call_args.kwargs["radius"] == mock_settings.max_radius_meters


@pytest.mark.asyncio
async def test_places_no_client_side_keyword_filter(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """The fork's headline fix: Text Search matches keywords server-side, so results
    whose *name* doesn't literally contain the keyword are still returned (upstream's
    Nearby Search + substring filter wrongly dropped these, e.g. "gas station")."""
    mock_gmaps_client.places.return_value = {
        "results": [
            {
                "name": "Shell",
                "formatted_address": "1 A St",
                "geometry": {"location": {"lat": 1, "lng": 2}},
                "types": ["gas_station"],
                "place_id": "p1",
            },
            {
                "name": "BP",
                "formatted_address": "2 B St",
                "geometry": {"location": {"lat": 3, "lng": 4}},
                "types": ["gas_station"],
                "place_id": "p2",
            },
        ]
    }
    tool = PlacesTool(mock_settings)

    result = await tool.execute({"location": "1,2", "keyword": "gas station"})

    names = [p["name"] for p in result["data"]["places"]]
    assert names == ["Shell", "BP"]  # neither name contains "gas station" — both kept
    assert mock_gmaps_client.places.call_args.kwargs["query"] == "gas station"


@pytest.mark.asyncio
async def test_places_empty_results(mock_settings: Settings, mock_gmaps_client: MagicMock) -> None:
    """No results → success with an empty list."""
    mock_gmaps_client.places.return_value = {"results": []}
    tool = PlacesTool(mock_settings)

    result = await tool.execute({"location": "40.7128,-74.0060", "keyword": "nothing"})

    assert result["status"] == "success"
    assert result["data"]["places"] == []
    assert result["data"]["count"] == 0


@pytest.mark.asyncio
async def test_places_handles_api_error_gracefully(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """``googlemaps.exceptions.ApiError`` is caught and returned as an error response."""
    mock_gmaps_client.places.side_effect = googlemaps.exceptions.ApiError("PERMISSION_DENIED")
    tool = PlacesTool(mock_settings)

    result = await tool.execute({"location": "40.7128,-74.0060", "keyword": "restaurant"})

    assert result["status"] == "error"
    assert "PERMISSION_DENIED" in result["error"]
    assert result["tool"] == "search_places"


@pytest.mark.asyncio
async def test_places_handles_multiple_api_errors(
    mock_settings: Settings, mock_gmaps_client: MagicMock
) -> None:
    """Various ApiError statuses surface in the error response."""
    tool = PlacesTool(mock_settings)

    for error_msg in ("PERMISSION_DENIED", "REQUEST_DENIED", "OVER_QUERY_LIMIT", "INVALID_REQUEST"):
        mock_gmaps_client.places.side_effect = googlemaps.exceptions.ApiError(error_msg)

        result = await tool.execute({"location": "40.7128,-74.0060", "keyword": "restaurant"})

        assert result["status"] == "error"
        assert error_msg in result["error"]
        assert result["tool"] == "search_places"
