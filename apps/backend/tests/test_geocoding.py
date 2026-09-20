"""Geocoding normalization tests / 地址定位正規化測試。"""

from api.geocoding import normalize_taiwan_address


def test_normalize_taiwan_address_reorders_postal_code_and_house_number() -> None:
    # Nominatim matches Taiwanese addresses more reliably in house-number-first order.
    # Nominatim 對門牌號碼在前的台灣地址格式命中率較高。
    assert normalize_taiwan_address("320桃園市中壢區普忠里中北路200號") == (
        "200, 中北路, 桃園市中壢區普忠里"
    )
