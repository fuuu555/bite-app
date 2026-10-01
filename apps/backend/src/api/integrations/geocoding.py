"""Replaceable geocoding boundary / 可替換的地址定位邊界。"""

from __future__ import annotations

import re
from typing import Any, Protocol

import httpx

from api.core.config import get_settings
from api.domain.schemas import GeocodingCandidate


class GeocodingProvider(Protocol):
    """Only providers whose licence permits storage may implement this interface.

    僅授權允許保存結果的 Provider 才能實作此介面。
    """

    @property
    def configured(self) -> bool: ...

    async def geocode(self, address: str) -> list[GeocodingCandidate]: ...

    async def reverse(self, latitude: float, longitude: float) -> str | None: ...


class UnconfiguredGeocodingProvider:
    @property
    def configured(self) -> bool:
        return False

    async def geocode(self, address: str) -> list[GeocodingCandidate]:
        del address
        return []

    async def reverse(self, latitude: float, longitude: float) -> str | None:
        del latitude, longitude
        return None


class NominatimGeocodingProvider:
    """OpenStreetMap Nominatim adapter / OpenStreetMap Nominatim 轉接器。"""

    endpoint = "https://nominatim.openstreetmap.org"

    @property
    def configured(self) -> bool:
        return True

    async def geocode(self, address: str) -> list[GeocodingCandidate]:
        # Taiwan addresses are commonly written as postal-code + city + road + number,
        # while Nominatim indexes them more reliably as number + road + administrative areas.
        # 台灣地址常寫成郵遞區號＋縣市＋道路＋門牌，但 Nominatim 對門牌＋道路＋行政區較容易命中。
        query = normalize_taiwan_address(address)
        data = await self._request(
            "/search",
            {"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "tw"},
        )
        return [
            GeocodingCandidate(
                label=str(item.get("display_name", "")),
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
            )
            for item in data
            if item.get("display_name") and item.get("lat") and item.get("lon")
        ]

    async def reverse(self, latitude: float, longitude: float) -> str | None:
        data = await self._request(
            "/reverse",
            {
                "lat": latitude,
                "lon": longitude,
                "format": "jsonv2",
                "zoom": 18,
                "addressdetails": 1,
            },
        )
        return format_taiwan_reverse_address(data)

    async def _request(self, path: str, params: dict[str, str | int | float]) -> Any:
        settings = get_settings()
        headers = {
            "User-Agent": settings.geocoding_user_agent,
            "Accept-Language": "zh-TW,zh;q=0.9",
        }
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            response = await client.get(f"{self.endpoint}{path}", params=params)
            response.raise_for_status()
            return response.json()


def get_geocoding_provider() -> GeocodingProvider:
    """Build the configured provider / 建立設定中的地址定位 Provider。"""
    provider = get_settings().geocoding_provider.lower()
    if provider == "nominatim":
        return NominatimGeocodingProvider()
    return UnconfiguredGeocodingProvider()


def normalize_taiwan_address(address: str) -> str:
    """Normalize common Taiwan address order for geocoding / 正規化台灣常見地址格式。"""
    normalized = re.sub(r"^\s*\d{3,6}\s*", "", address.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    # Some map exports omit 「號」, such as 「忠孝東路五段159」.
    # 部分地圖資料不會附上「號」，例如「忠孝東路五段159」。
    number_match = re.search(r"(?P<number>\d{1,4}(?:[-－之]\d{1,4})?)(?:號)?", normalized)
    if number_match:
        before_number = normalized[: number_match.start()]
        separator_positions = [
            before_number.rfind(separator) for separator in ("里", "區", "市", "鄉", "鎮")
        ]
        separator_position = max(separator_positions)
        if separator_position >= 0:
            prefix = before_number[: separator_position + 1].strip(" ,")
            road = _normalize_unmarked_neighborhood(before_number, separator_position)
            number = number_match.group("number")
            suffix = normalized[number_match.end() :].strip(" ,")
            if road:
                parts = [f"{number}, {road}", prefix, suffix]
                return ", ".join(part for part in parts if part)
    return normalized


def _normalize_unmarked_neighborhood(before_number: str, separator_position: int) -> str:
    """Remove a two-character locality stuck to a road / 移除與道路相黏的兩字地名。"""
    road = before_number[separator_position + 1 :].strip(" ,")
    if "里" in before_number or "村" in before_number:
        return road

    road_name = re.match(r"(?P<name>[\u4e00-\u9fff]+)(?:路|街|大道)", road)
    if road_name and len(road_name.group("name")) >= 5:
        # Nominatim recognizes 「忠孝東路」 but not 「興雅忠孝東路」;
        # the first two characters are often an unmarked neighbourhood name.
        # Nominatim 能辨識「忠孝東路」，但不會把「興雅忠孝東路」當道路；
        # 前兩字通常是沒有「里」字的地名。
        return road[2:]
    return road


def format_taiwan_reverse_address(data: Any) -> str | None:
    """Return a Taiwan-style address from Nominatim details / 將 Nominatim 結果轉為台灣常用地址。"""
    address = data.get("address") if isinstance(data, dict) else None
    if not isinstance(address, dict):
        label = data.get("display_name") if isinstance(data, dict) else None
        return str(label) if label else None

    # Reverse geocoding returns administrative layers in a provider-specific order.
    # 將 Provider 的行政層級重排為管理員與 Google 地圖常用的台灣地址順序。
    postcode = _address_part(address, "postcode")
    city = _address_part(address, "city", "county", "municipality")
    district = _address_part(address, "city_district", "district", "suburb", "town")
    village = _address_part(address, "village", "neighbourhood", "quarter")
    road = _address_part(address, "road", "residential", "pedestrian")
    house_number = _address_part(address, "house_number")
    parts = [postcode, city, district, village, road, house_number]
    formatted = "".join(part for part in parts if part)
    if formatted and (road or house_number):
        return formatted

    label = data.get("display_name")
    return str(label) if label else None


def _address_part(address: dict[str, Any], *keys: str) -> str:
    """Read the first non-empty Nominatim address field / 讀取第一個有效地址欄位。"""
    for key in keys:
        value = address.get(key)
        if value:
            return str(value).strip()
    return ""
