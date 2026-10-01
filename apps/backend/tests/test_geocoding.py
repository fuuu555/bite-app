"""Geocoding normalization tests / 地址定位正規化測試。"""

from api.integrations.geocoding import format_taiwan_reverse_address, normalize_taiwan_address


def test_normalize_taiwan_address_reorders_postal_code_and_house_number() -> None:
    # Nominatim matches Taiwanese addresses more reliably in house-number-first order.
    # Nominatim 對門牌號碼在前的台灣地址格式命中率較高。
    assert normalize_taiwan_address("320桃園市中壢區普忠里中北路200號") == (
        "200, 中北路, 桃園市中壢區普忠里"
    )


def test_normalize_taiwan_address_preserves_compound_house_number() -> None:
    assert normalize_taiwan_address("桃園市中壢區普仁里新中北路151-1號一樓") == (
        "151-1, 新中北路, 桃園市中壢區普仁里, 一樓"
    )


def test_normalize_taiwan_address_handles_postcode_and_unmarked_neighborhood() -> None:
    assert normalize_taiwan_address("110臺北市信義區興雅忠孝東路五段159") == (
        "159, 忠孝東路五段, 臺北市信義區"
    )


def test_format_taiwan_reverse_address_reorders_nominatim_layers() -> None:
    result = format_taiwan_reverse_address(
        {
            "address": {
                "house_number": "331之3號",
                "road": "撫遠街",
                "neighbourhood": "水族街",
                "village": "新益里",
                "suburb": "松山區",
                "city": "臺北市",
                "postcode": "105",
                "country": "臺灣",
            }
        }
    )
    assert result == "105臺北市松山區新益里撫遠街331之3號"
