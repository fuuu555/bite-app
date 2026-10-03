"""Grounded travel itinerary recommendations / 有來源追溯的旅遊行程推薦。"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Any, cast

import httpx
from geoalchemy2 import Geography
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.core.config import Settings
from api.domain.models import Restaurant, TourismSourcePlace
from api.domain.schemas import (
    ItineraryDuration,
    ItineraryIntentResponse,
    ItineraryPlaceResponse,
    ItineraryPlanRequest,
    ItineraryPlanResponse,
    ItineraryPlanSource,
    ItineraryQuickAction,
    ItineraryStopResponse,
    ItineraryTransport,
    TourismPlaceCategory,
    TourismSourceDataset,
)


@dataclass(frozen=True)
class CityCenter:
    name: str
    latitude: float
    longitude: float


TAIWAN_CITY_CENTERS: tuple[CityCenter, ...] = (
    CityCenter("台北市", 25.0375, 121.5637),
    CityCenter("新北市", 25.0118, 121.4657),
    CityCenter("桃園市", 24.9937, 121.3010),
    CityCenter("台中市", 24.1477, 120.6736),
    CityCenter("台南市", 22.9997, 120.2270),
    CityCenter("高雄市", 22.6273, 120.3014),
    CityCenter("基隆市", 25.1276, 121.7392),
    CityCenter("新竹市", 24.8138, 120.9675),
    CityCenter("嘉義市", 23.4801, 120.4491),
    CityCenter("新竹縣", 24.8387, 121.0177),
    CityCenter("苗栗縣", 24.5602, 120.8214),
    CityCenter("彰化縣", 24.0755, 120.5440),
    CityCenter("南投縣", 23.9609, 120.9719),
    CityCenter("雲林縣", 23.7092, 120.4313),
    CityCenter("嘉義縣", 23.4586, 120.2919),
    CityCenter("屏東縣", 22.5519, 120.5487),
    CityCenter("宜蘭縣", 24.7021, 121.7378),
    CityCenter("花蓮縣", 23.9911, 121.6112),
    CityCenter("台東縣", 22.7554, 121.1505),
    CityCenter("澎湖縣", 23.5711, 119.5793),
    CityCenter("金門縣", 24.4493, 118.3767),
    CityCenter("連江縣", 26.1605, 119.9510),
)

CITY_ALIASES = {"臺": "台"}
DEFAULT_RADIUS_KM = 5


@dataclass(frozen=True)
class ParsedIntent:
    city: str | None
    duration: ItineraryDuration
    transport: ItineraryTransport
    interests: list[str]
    meal_preference: str | None
    include_lodging: bool
    source: ItineraryPlanSource


def _normalize_city(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    for source, target in CITY_ALIASES.items():
        normalized = normalized.replace(source, target)
    return normalized


def _find_city(value: str | None) -> CityCenter | None:
    if not value:
        return None
    normalized = _normalize_city(value)
    return next(
        (city for city in TAIWAN_CITY_CENTERS if city.name == normalized),
        None,
    )


def resolve_origin(
    request: ItineraryPlanRequest,
    *,
    city_override: str | None = None,
) -> tuple[float, float, str | None]:
    """Resolve coordinates without geocoding or inventing an address."""
    if request.latitude is not None and request.longitude is not None:
        return request.latitude, request.longitude, request.city
    city = _find_city(city_override or request.city)
    if city is None:
        raise ValueError("unsupported city; choose a Taiwan city or provide coordinates")
    return city.latitude, city.longitude, city.name


def parse_rules_prompt(prompt: str | None, city: str | None) -> ParsedIntent:
    """Parse common Traditional Chinese travel phrases deterministically."""
    text = _normalize_city(prompt or "")
    duration: ItineraryDuration = (
        "full_day" if any(item in text for item in ("一日", "整天", "全天")) else "half_day"
    )
    transport: ItineraryTransport = "driving"
    if any(item in text for item in ("不開車", "大眾運輸", "公車", "火車", "捷運")):
        transport = "public_transport"
    elif any(item in text for item in ("步行", "走路")):
        transport = "walking"

    interests = [
        label
        for keywords, label in (
            (("自然", "山", "海", "湖"), "自然"),
            (("文化", "古蹟", "歷史"), "文化"),
            (("親子", "小孩"), "親子"),
            (("美食", "吃", "餐"), "美食"),
        )
        if any(keyword in text for keyword in keywords)
    ]
    meal_preference = "素食" if any(item in text for item in ("素食", "吃素", "蔬食")) else None
    include_lodging = any(
        item in text for item in ("住宿", "旅館", "民宿", "住一晚", "住附近")
    )
    parsed_city = next(
        (
            item.name
            for item in TAIWAN_CITY_CENTERS
            if item.name in text or item.name[:-1] in text
        ),
        city,
    )
    return ParsedIntent(
        city=parsed_city,
        duration=duration,
        transport=transport,
        interests=interests,
        meal_preference=meal_preference,
        include_lodging=include_lodging,
        source="rules",
    )


async def parse_ai_prompt(
    prompt: str | None,
    *,
    city: str | None,
    settings: Settings,
) -> ParsedIntent | None:
    """Use an optional OpenAI-compatible JSON endpoint, then let callers fall back safely."""
    if not prompt or not settings.ai_api_key or not settings.ai_model:
        return None

    system_prompt = (
        "你是台灣旅遊需求解析器。只回傳 JSON，不要 Markdown。欄位為："
        "city(string|null), duration(half_day|full_day), "
        "transport(walking|public_transport|driving), "
        "interests(string[]), meal_preference(string|null), include_lodging(boolean)。"
        "不要產生景點名稱、店家名稱或任何資料庫外地點。"
    )
    payload = {
        "model": settings.ai_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            response = await client.post(
                f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.ai_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return ParsedIntent(
                city=_optional_text(parsed.get("city")) or city,
                duration=_duration(parsed.get("duration")),
                transport=_transport(parsed.get("transport")),
                interests=_string_list(parsed.get("interests"))[:5],
                meal_preference=_optional_text(parsed.get("meal_preference")),
                include_lodging=bool(parsed.get("include_lodging", False)),
                source="ai",
            )
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


async def plan_itinerary(
    session: AsyncSession,
    request: ItineraryPlanRequest,
    *,
    settings: Settings,
) -> ItineraryPlanResponse:
    """Create quick recommendations or an ordered plan from grounded records."""
    rules_intent = parse_rules_prompt(request.prompt, request.city)
    latitude, longitude, resolved_city = resolve_origin(
        request,
        city_override=request.city or rules_intent.city,
    )
    ai_intent = await parse_ai_prompt(request.prompt, city=resolved_city, settings=settings)
    parsed = ai_intent or parse_rules_prompt(request.prompt, resolved_city)
    quick_action = request.quick_action
    include_lodging = request.include_lodging or parsed.include_lodging or quick_action == "stay"
    categories, datasets = _filters_for_action(quick_action, include_lodging)

    restaurants = await _query_restaurants(
        session,
        latitude=latitude,
        longitude=longitude,
        radius_km=request.radius_km,
        limit=8,
    ) if quick_action in {"eat", "plan"} else []
    tourism_places = await _query_tourism_places(
        session,
        latitude=latitude,
        longitude=longitude,
        radius_km=request.radius_km,
        categories=categories,
        datasets=datasets,
        limit=16,
    )

    all_candidates = sorted(
        [*restaurants, *tourism_places],
        key=lambda item: (item.distance_meters, item.name.casefold(), str(item.id)),
    )
    stops = _build_stops(
        quick_action=quick_action,
        duration=request.duration if not request.prompt else parsed.duration,
        include_lodging=include_lodging,
        candidates=all_candidates,
        interests=parsed.interests,
        meal_preference=request.meal_preference or parsed.meal_preference,
        transport=request.transport if not request.prompt else parsed.transport,
    )
    stop_ids = {stop.place.id for stop in stops}
    alternatives = [item for item in all_candidates if item.id not in stop_ids][:8]
    title, summary = _plan_copy(
        quick_action=quick_action,
        city=resolved_city,
        stop_count=len(stops),
        source=parsed.source,
    )
    intent = ItineraryIntentResponse(
        city=parsed.city,
        duration=request.duration if not request.prompt else parsed.duration,
        transport=request.transport if not request.prompt else parsed.transport,
        interests=parsed.interests,
        meal_preference=request.meal_preference or parsed.meal_preference,
        include_lodging=include_lodging,
    )
    return ItineraryPlanResponse(
        source=parsed.source,
        title=title,
        summary=summary,
        center_latitude=latitude,
        center_longitude=longitude,
        city=resolved_city,
        radius_km=request.radius_km,
        intent=intent,
        stops=stops,
        alternatives=alternatives,
    )


def _filters_for_action(
    quick_action: ItineraryQuickAction,
    include_lodging: bool,
) -> tuple[list[TourismPlaceCategory] | None, list[TourismSourceDataset] | None]:
    if quick_action == "stay":
        return ["hotel"], ["hotel"]
    if quick_action == "attraction":
        return ["attraction"], ["attraction"]
    if quick_action == "eat":
        return ["restaurant"], ["food"]
    datasets: list[TourismSourceDataset] = ["attraction", "food"]
    categories: list[TourismPlaceCategory] = ["attraction", "restaurant"]
    if include_lodging:
        datasets.append("hotel")
        categories.append("hotel")
    return categories, datasets


async def _query_restaurants(
    session: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    radius_km: int,
    limit: int,
) -> list[ItineraryPlaceResponse]:
    origin = _origin_point(latitude, longitude)
    statement: Select[Any] = (
        select(Restaurant)
        .options(selectinload(Restaurant.primary_cuisine))
        .add_columns(func.ST_Distance(Restaurant.location, origin))
        .where(
            Restaurant.status == "published",
            Restaurant.location.is_not(None),
            func.ST_DWithin(Restaurant.location, origin, radius_km * 1000),
        )
        .order_by(func.ST_Distance(Restaurant.location, origin), Restaurant.name)
        .limit(limit)
    )
    rows = list((await session.execute(statement)).all())
    return [
        ItineraryPlaceResponse(
            id=restaurant.id,
            source="bitemap",
            source_dataset="bitemap",
            source_record_id=None,
            category="restaurant",
            name=restaurant.name,
            address=restaurant.address,
            latitude=restaurant.latitude,
            longitude=restaurant.longitude,
            distance_meters=float(distance),
            cuisine_name=(
                restaurant.primary_cuisine.display_name if restaurant.primary_cuisine else None
            ),
            price_range=cast(Any, restaurant.price_range),
            icon_color=(
                restaurant.primary_cuisine.color if restaurant.primary_cuisine else "#F26B4F"
            ),
        )
        for restaurant, distance in rows
        if restaurant.latitude is not None and restaurant.longitude is not None
    ]


async def _query_tourism_places(
    session: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    radius_km: int,
    categories: list[TourismPlaceCategory] | None,
    datasets: list[TourismSourceDataset] | None,
    limit: int,
) -> list[ItineraryPlaceResponse]:
    origin = _origin_point(latitude, longitude)
    statement: Select[Any] = (
        select(TourismSourcePlace)
        .add_columns(func.ST_Distance(TourismSourcePlace.location, origin))
        .where(
            TourismSourcePlace.status == "active",
            TourismSourcePlace.is_map_enabled.is_(True),
            TourismSourcePlace.location.is_not(None),
            func.ST_DWithin(TourismSourcePlace.location, origin, radius_km * 1000),
        )
        .order_by(func.ST_Distance(TourismSourcePlace.location, origin), TourismSourcePlace.name)
        .limit(limit)
    )
    if categories:
        statement = statement.where(TourismSourcePlace.category.in_(categories))
    if datasets:
        statement = statement.where(TourismSourcePlace.source_dataset.in_(datasets))
    rows = list((await session.execute(statement)).all())
    return [
        ItineraryPlaceResponse(
            id=place.id,
            source="tourism",
            source_dataset=cast(TourismSourceDataset, place.source_dataset),
            source_record_id=place.source_record_id,
            category=cast(TourismPlaceCategory, place.category),
            name=place.display_name or place.name,
            address=place.display_address or place.address,
            latitude=place.latitude,
            longitude=place.longitude,
            distance_meters=float(distance),
            description=place.description,
            phone=place.phone,
            official_url=place.official_url,
            opening_hours=place.opening_hours,
            source_updated_at=place.source_updated_at,
            tags=cast(list[str], place.tags),
            icon_color=place.icon_color,
        )
        for place, distance in rows
        if place.latitude is not None and place.longitude is not None
    ]


def _build_stops(
    *,
    quick_action: ItineraryQuickAction,
    duration: ItineraryDuration,
    include_lodging: bool,
    candidates: list[ItineraryPlaceResponse],
    interests: list[str],
    meal_preference: str | None,
    transport: ItineraryTransport,
) -> list[ItineraryStopResponse]:
    if quick_action in {"eat", "stay", "attraction"}:
        role = {"eat": "meal", "stay": "lodging", "attraction": "attraction"}[quick_action]
        return [
            ItineraryStopResponse(
                order=index,
                role=cast(Any, role),
                reason=_reason_for_place(
                    place,
                    interests=interests,
                    meal_preference=meal_preference,
                ),
                suggested_duration_minutes=90 if role == "meal" else 120,
                place=place,
            )
            for index, place in enumerate(candidates[:5], start=1)
        ]

    attractions = [item for item in candidates if item.category == "attraction"]
    meals = [item for item in candidates if item.category == "restaurant"]
    hotels = [item for item in candidates if item.category == "hotel"]
    selected: list[tuple[str, ItineraryPlaceResponse, int]] = []
    if attractions:
        selected.append(("attraction", attractions[0], 150))
    if duration == "full_day" and len(attractions) > 1:
        selected.append(("attraction", attractions[1], 120))
    if meals:
        selected.append(("meal", meals[0], 90))
    if include_lodging and hotels:
        selected.append(("lodging", hotels[0], 480))
    return [
        ItineraryStopResponse(
            order=index,
            role=cast(Any, role),
            reason=_reason_for_place(
                place,
                interests=interests,
                meal_preference=meal_preference,
                transport=transport,
            ),
            suggested_duration_minutes=minutes,
            place=place,
        )
        for index, (role, place, minutes) in enumerate(selected, start=1)
    ]


def _reason_for_place(
    place: ItineraryPlaceResponse,
    *,
    interests: list[str],
    meal_preference: str | None,
    transport: ItineraryTransport | None = None,
) -> str:
    if place.category == "hotel":
        return "使用觀光署旅館民宿資料，距離目前位置較近。"
    if place.category == "restaurant":
        preference = f"，符合{meal_preference}偏好" if meal_preference else ""
        return f"距離目前位置約 {max(1, round(place.distance_meters))} 公尺{preference}。"
    interest = f"，符合「{interests[0]}」方向" if interests else ""
    transport_note = (
        "，並優先考慮短距離移動"
        if transport in {"walking", "public_transport"}
        else ""
    )
    return f"可作為附近旅遊節點{interest}{transport_note}。"


def _plan_copy(
    *,
    quick_action: ItineraryQuickAction,
    city: str | None,
    stop_count: int,
    source: ItineraryPlanSource,
) -> tuple[str, str]:
    location = city or "目前位置"
    source_label = "AI 解析" if source == "ai" else "智慧推薦"
    if quick_action == "eat":
        return "附近吃飯推薦", f"{source_label}已從{location}附近找到 {stop_count} 個餐飲選項。"
    if quick_action == "stay":
        return (
            "附近住宿推薦",
            f"{source_label}只使用觀光署旅館民宿資料，整理出 {stop_count} 個附近選項。",
        )
    if quick_action == "attraction":
        return "附近景點推薦", f"{source_label}已從{location}附近找到 {stop_count} 個景點選項。"
    return "你的附近旅遊行程", f"{source_label}已組合 {stop_count} 個可追溯至地圖資料的行程節點。"


def _origin_point(latitude: float, longitude: float):
    return func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(
        Geography(geometry_type="POINT", srid=4326)
    )


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _duration(value: object) -> ItineraryDuration:
    return "full_day" if value == "full_day" else "half_day"


def _transport(value: object) -> ItineraryTransport:
    if value in {"walking", "driving"}:
        return cast(ItineraryTransport, value)
    return "public_transport"
