"""Google Places API integration / Google Places API 整合。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from api.core.config import get_settings
from api.domain.schemas import ExploreGoogleSignalsResponse

logger = logging.getLogger(__name__)

PLACES_BASE_URL = "https://places.googleapis.com/v1"
SEARCH_FIELD_MASK = "places.id"
DETAIL_FIELD_MASK = "rating,userRatingCount"


@dataclass(frozen=True, slots=True)
class GooglePlaceLookup:
    """Restaurant fields needed to resolve Google Places signals."""

    place_id: str | None
    name: str
    address: str
    latitude: float | None = None
    longitude: float | None = None


async def _search_place_id(
    client: httpx.AsyncClient,
    *,
    name: str,
    address: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> str | None:
    search_payload: dict[str, object] = {
        "textQuery": f"{name} {address}".strip(),
        "languageCode": "zh-TW",
        "regionCode": "TW",
    }
    if latitude is not None and longitude is not None:
        search_payload["locationBias"] = {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": 1000,
            }
        }

    headers = {
        "X-Goog-Api-Key": get_settings().google_places_api_key or "",
        "X-Goog-FieldMask": SEARCH_FIELD_MASK,
    }

    search_response = await client.post(
        f"{PLACES_BASE_URL}/places:searchText",
        headers=headers,
        json=search_payload,
    )
    search_response.raise_for_status()
    places = search_response.json().get("places", [])
    if not places:
        return None
    place_id = places[0].get("id")
    return place_id if isinstance(place_id, str) and place_id else None


async def find_google_place_id(
    *,
    name: str,
    address: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> str | None:
    """Find and return one Google Place ID for an admin restaurant mapping."""
    if not get_settings().google_places_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            return await _search_place_id(
                client,
                name=name,
                address=address,
                latitude=latitude,
                longitude=longitude,
            )
    except (httpx.HTTPError, ValueError, TypeError) as error:
        logger.warning("Google Places search failed: %s", type(error).__name__)
        return None


async def fetch_google_signals(
    *,
    place_id: str | None,
    name: str,
    address: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> ExploreGoogleSignalsResponse | None:
    """Fetch only rating/count, using a stored ID or an on-demand fallback.

    使用已保存的 Place ID；舊店家尚未綁定時才用店名與地址暫時解析。
    不抓評論、不保存 Google response。
    """
    results = await fetch_google_signals_batch(
        [
            GooglePlaceLookup(
                place_id=place_id,
                name=name,
                address=address,
                latitude=latitude,
                longitude=longitude,
            )
        ]
    )
    return results[0]


async def fetch_google_signals_batch(
    lookups: Sequence[GooglePlaceLookup],
) -> list[ExploreGoogleSignalsResponse | None]:
    """Fetch Google rating/count for multiple restaurants with one HTTP client."""
    if not lookups:
        return []
    api_key = get_settings().google_places_api_key
    if not api_key:
        return [None] * len(lookups)

    async with httpx.AsyncClient(timeout=8.0) as client:
        return list(
            await asyncio.gather(
                *(
                    _fetch_google_signals_with_client(client, lookup, api_key)
                    for lookup in lookups
                )
            )
        )


async def _fetch_google_signals_with_client(
    client: httpx.AsyncClient,
    lookup: GooglePlaceLookup,
    api_key: str,
) -> ExploreGoogleSignalsResponse | None:
    try:
        resolved_place_id = lookup.place_id or await _search_place_id(
            client,
            name=lookup.name,
            address=lookup.address,
            latitude=lookup.latitude,
            longitude=lookup.longitude,
        )
        if not resolved_place_id:
            return None
        detail_response = await client.get(
            f"{PLACES_BASE_URL}/places/{quote(resolved_place_id, safe='')}",
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": DETAIL_FIELD_MASK,
            },
        )
        detail_response.raise_for_status()
        detail = detail_response.json()
    except (httpx.HTTPError, ValueError, TypeError) as error:
        logger.warning("Google Places lookup failed: %s", type(error).__name__)
        return None

    rating = detail.get("rating")
    review_count = detail.get("userRatingCount")
    return ExploreGoogleSignalsResponse(
        rating=float(rating) if isinstance(rating, (int, float)) else None,
        review_count=int(review_count) if isinstance(review_count, int) else None,
    )
