"""Places API tool implementations."""

import asyncio
from typing import Any

import googlemaps
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseTool

logger = structlog.get_logger()


class PlacesTool(BaseTool):
    """Search for nearby places using Google Places API."""

    @property
    def name(self) -> str:
        return "search_places"

    @property
    def description(self) -> str:
        return (
            "Search for nearby places based on location and keywords. "
            "Returns place names, addresses, ratings, and other details."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location as 'lat,lng' (e.g., '37.7749,-122.4194')",
                },
                "keyword": {
                    "type": "string",
                    "description": "Keyword to search for (e.g., 'gas station', 'restaurant')",
                },
                "radius": {
                    "type": "integer",
                    "default": 5000,
                    "description": "Search radius in meters (default: 5000, max: 50000)",
                },
                "type": {
                    "type": "string",
                    "description": "Place type (e.g., 'restaurant', 'gas_station', 'parking')",
                },
            },
            "required": ["location", "keyword"],
        }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute nearby places search using the new Places API."""
        try:
            location = arguments["location"]
            keyword = arguments["keyword"]
            radius = min(
                arguments.get("radius", self.settings.default_radius_meters),
                self.settings.max_radius_meters,
            )
            place_type = arguments.get("type")

            logger.info(
                "searching_places",
                location=location,
                keyword=keyword,
                radius=radius,
                type=place_type,
            )

            # Parse location (lat,lng)
            lat_str, lng_str = location.split(",")
            lat = float(lat_str.strip())
            lng = float(lng_str.strip())

            # Execute via Places Text Search (keyword-native — no client-side filter)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._search_text(lat, lng, radius, keyword, place_type),
            )

            # Format response
            places = result[: self.settings.max_results]

            logger.info("places_found", count=len(places))
            return self._format_response({"places": places, "count": len(places)})

        except googlemaps.exceptions.ApiError as e:
            # Handle API errors gracefully (e.g., PERMISSION_DENIED, REQUEST_DENIED)
            error_msg = str(e)
            logger.error("places_search_failed", error=error_msg)
            return self._format_response(None, status="error", error=error_msg)
        except Exception as e:
            logger.error("places_search_failed", error=str(e))
            return self._format_response(None, status="error", error=str(e))

    def _search_text(
        self,
        lat: float,
        lng: float,
        radius: float,
        keyword: str,
        place_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search places via the Places API **Text Search** (``gmaps.places``).

        OtoDock fork fix: upstream used Nearby Search + a client-side substring
        keyword filter, which dropped legitimate multi-word matches (e.g. "gas
        station"). Text Search handles keywords natively — no client-side
        filtering — and rides the same ``self.gmaps`` client, so it works through
        the OtoDock relay (hosted) or a BYO key transparently.
        """
        kwargs: dict[str, Any] = {
            "query": keyword,
            "location": (lat, lng),
            "radius": int(radius),
        }
        if place_type:
            kwargs["type"] = place_type

        result = self.gmaps.places(**kwargs)

        places: list[dict[str, Any]] = []
        for place in (result.get("results") or [])[: self.settings.max_results]:
            loc = (place.get("geometry") or {}).get("location") or {}
            places.append(
                {
                    "name": place.get("name"),
                    "address": place.get("formatted_address") or place.get("vicinity"),
                    "location": {"lat": loc.get("lat"), "lng": loc.get("lng")},
                    "rating": place.get("rating"),
                    "types": place.get("types") or [],
                    "place_id": place.get("place_id"),
                }
            )

        return places


class PlaceDetailsTool(BaseTool):
    """Get detailed information about a place using Google Places API."""

    @property
    def name(self) -> str:
        return "get_place_details"

    @property
    def description(self) -> str:
        return (
            "Get detailed information about a specific place using its Place ID. "
            "Returns address, phone number, website, opening hours, and other details."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "place_id": {
                    "type": "string",
                    "description": "The unique Place ID",
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific fields to retrieve (optional)",
                },
            },
            "required": ["place_id"],
        }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute place details request."""
        try:
            place_id = arguments["place_id"]
            fields = arguments.get("fields")

            logger.info("getting_place_details", place_id=place_id, fields=fields)

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._get_place_details(place_id, fields),
            )

            logger.info("place_details_retrieved", place_id=place_id)
            return self._format_response(result)

        except googlemaps.exceptions.ApiError as e:
            error_msg = str(e)
            logger.error("place_details_failed", error=error_msg)
            return self._format_response(None, status="error", error=error_msg)
        except Exception as e:
            logger.error("place_details_failed", error=str(e))
            return self._format_response(None, status="error", error=str(e))

    def _get_place_details(
        self, place_id: str, fields: list[str] | None = None
    ) -> dict[str, Any]:
        """Get place details via the Places API Details endpoint (``gmaps.place``).

        OtoDock fork: uses the same ``self.gmaps`` client (relay-aware) as the rest
        of the tools — no separate gapic client. Friendly short field names are
        mapped to the lib's field names; unknown names pass through.
        """
        field_map = {
            "name": "name",
            "address": "formatted_address",
            "location": "geometry",
            "rating": "rating",
            "types": "type",
            "id": "place_id",
            "phone": "formatted_phone_number",
            "website": "website",
            "hours": "opening_hours",
            "price": "price_level",
            "reviews": "user_ratings_total",
        }
        default_fields = [
            "name", "formatted_address", "geometry", "rating", "type", "place_id",
            "formatted_phone_number", "website", "opening_hours", "price_level",
            "user_ratings_total",
        ]
        lib_fields = (
            [field_map.get(f, f) for f in fields] if fields else default_fields
        )

        result = self.gmaps.place(place_id=place_id, fields=lib_fields)
        r = result.get("result") or {}
        loc = (r.get("geometry") or {}).get("location") or {}

        place_data: dict[str, Any] = {
            "name": r.get("name"),
            "address": r.get("formatted_address"),
            "location": {"lat": loc.get("lat"), "lng": loc.get("lng")},
            "rating": r.get("rating"),
            "types": r.get("types") or [],
            "place_id": r.get("place_id"),
            "phone_number": r.get("formatted_phone_number"),
            "website": r.get("website"),
            "price_level": r.get("price_level"),
            "user_ratings_total": r.get("user_ratings_total"),
        }

        opening = r.get("opening_hours")
        if opening:
            place_data["opening_hours"] = {
                "open_now": opening.get("open_now"),
                "weekday_text": opening.get("weekday_text") or [],
            }

        return place_data


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def search_nearby(gmaps: googlemaps.Client, params: dict[str, Any]) -> dict[str, Any]:
    """Search for nearby places with retry logic"""

    # Run in executor since googlemaps is synchronous
    loop = asyncio.get_event_loop()

    result = await loop.run_in_executor(
        None,
        lambda: gmaps.places_nearby(
            location=params["location"],
            keyword=params["keyword"],
            radius=params.get("radius", 5000),
            type=params.get("type"),
        ),
    )

    # Clean and format response for fleet safety context
    places = []
    for place in result.get("results", [])[:10]:  # Limit results
        places.append(
            {
                "name": place.get("name"),
                "address": place.get("vicinity"),
                "location": place.get("geometry", {}).get("location"),
                "rating": place.get("rating"),
                "types": place.get("types", []),
                "place_id": place.get("place_id"),
            }
        )

    return {"status": "success", "count": len(places), "places": places}
