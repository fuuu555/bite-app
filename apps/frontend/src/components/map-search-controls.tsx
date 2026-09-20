"use client";

import {
  IconAdjustmentsHorizontal,
  IconMapPin,
  IconSearch,
  IconToolsKitchen3,
  IconX,
} from "@tabler/icons-react";

import {
  priceRangeLabels,
  type MapCuisine,
  type MapFilters,
  type MapRestaurant,
  type MapSearchLocation,
  type MapSearchResponse,
} from "@/lib/public-map-api";

const taiwanAdministrativeAreas: Record<string, readonly string[]> = {
  臺北市: [
    "松山區",
    "信義區",
    "大安區",
    "中山區",
    "中正區",
    "大同區",
    "萬華區",
    "文山區",
    "南港區",
    "內湖區",
    "士林區",
    "北投區",
  ],
  臺中市: [
    "中區",
    "東區",
    "南區",
    "西區",
    "北區",
    "西屯區",
    "南屯區",
    "北屯區",
    "豐原區",
    "東勢區",
    "大甲區",
    "清水區",
    "沙鹿區",
    "梧棲區",
    "后里區",
    "神岡區",
    "潭子區",
    "大雅區",
    "新社區",
    "石岡區",
    "外埔區",
    "大安區",
    "烏日區",
    "大肚區",
    "龍井區",
    "霧峰區",
    "太平區",
    "大里區",
    "和平區",
  ],
  基隆市: ["中正區", "七堵區", "暖暖區", "仁愛區", "中山區", "安樂區", "信義區"],
  臺南市: [
    "新營區",
    "鹽水區",
    "白河區",
    "柳營區",
    "後壁區",
    "東山區",
    "麻豆區",
    "下營區",
    "六甲區",
    "官田區",
    "大內區",
    "佳里區",
    "學甲區",
    "西港區",
    "七股區",
    "將軍區",
    "北門區",
    "新化區",
    "善化區",
    "新市區",
    "安定區",
    "山上區",
    "玉井區",
    "楠西區",
    "南化區",
    "左鎮區",
    "仁德區",
    "歸仁區",
    "關廟區",
    "龍崎區",
    "永康區",
    "東區",
    "南區",
    "北區",
    "安南區",
    "安平區",
    "中西區",
  ],
  高雄市: [
    "鹽埕區",
    "鼓山區",
    "左營區",
    "楠梓區",
    "三民區",
    "新興區",
    "前金區",
    "苓雅區",
    "前鎮區",
    "旗津區",
    "小港區",
    "鳳山區",
    "林園區",
    "大寮區",
    "大樹區",
    "大社區",
    "仁武區",
    "鳥松區",
    "岡山區",
    "橋頭區",
    "燕巢區",
    "田寮區",
    "阿蓮區",
    "路竹區",
    "湖內區",
    "茄萣區",
    "永安區",
    "彌陀區",
    "梓官區",
    "旗山區",
    "美濃區",
    "六龜區",
    "甲仙區",
    "杉林區",
    "內門區",
    "茂林區",
    "桃源區",
    "那瑪夏區",
  ],
  新北市: [
    "板橋區",
    "三重區",
    "中和區",
    "永和區",
    "新莊區",
    "新店區",
    "樹林區",
    "鶯歌區",
    "三峽區",
    "淡水區",
    "汐止區",
    "瑞芳區",
    "土城區",
    "蘆洲區",
    "五股區",
    "泰山區",
    "林口區",
    "深坑區",
    "石碇區",
    "坪林區",
    "三芝區",
    "石門區",
    "八里區",
    "平溪區",
    "雙溪區",
    "貢寮區",
    "金山區",
    "萬里區",
    "烏來區",
  ],
  宜蘭縣: [
    "宜蘭市",
    "羅東鎮",
    "蘇澳鎮",
    "頭城鎮",
    "礁溪鄉",
    "壯圍鄉",
    "員山鄉",
    "冬山鄉",
    "五結鄉",
    "三星鄉",
    "大同鄉",
    "南澳鄉",
  ],
  桃園市: [
    "桃園區",
    "中壢區",
    "大溪區",
    "楊梅區",
    "蘆竹區",
    "大園區",
    "龜山區",
    "八德區",
    "龍潭區",
    "平鎮區",
    "新屋區",
    "觀音區",
    "復興區",
  ],
  嘉義市: ["東區", "西區"],
  新竹縣: [
    "竹北市",
    "竹東鎮",
    "新埔鎮",
    "關西鎮",
    "湖口鄉",
    "新豐鄉",
    "芎林鄉",
    "橫山鄉",
    "北埔鄉",
    "寶山鄉",
    "峨眉鄉",
    "尖石鄉",
    "五峰鄉",
  ],
  苗栗縣: [
    "苗栗市",
    "苑裡鎮",
    "通霄鎮",
    "竹南鎮",
    "頭份市",
    "後龍鎮",
    "卓蘭鎮",
    "大湖鄉",
    "公館鄉",
    "銅鑼鄉",
    "南庄鄉",
    "頭屋鄉",
    "三義鄉",
    "西湖鄉",
    "造橋鄉",
    "三灣鄉",
    "獅潭鄉",
    "泰安鄉",
  ],
  南投縣: [
    "南投市",
    "埔里鎮",
    "草屯鎮",
    "竹山鎮",
    "集集鎮",
    "名間鄉",
    "鹿谷鄉",
    "中寮鄉",
    "魚池鄉",
    "國姓鄉",
    "水里鄉",
    "信義鄉",
    "仁愛鄉",
  ],
  彰化縣: [
    "彰化市",
    "鹿港鎮",
    "和美鎮",
    "線西鄉",
    "伸港鄉",
    "福興鄉",
    "秀水鄉",
    "花壇鄉",
    "芬園鄉",
    "員林市",
    "溪湖鎮",
    "田中鎮",
    "大村鄉",
    "埔鹽鄉",
    "埔心鄉",
    "永靖鄉",
    "社頭鄉",
    "二水鄉",
    "北斗鎮",
    "二林鎮",
    "田尾鄉",
    "埤頭鄉",
    "芳苑鄉",
    "大城鄉",
    "竹塘鄉",
    "溪州鄉",
  ],
  新竹市: ["東區", "北區", "香山區"],
  雲林縣: [
    "斗六市",
    "斗南鎮",
    "虎尾鎮",
    "西螺鎮",
    "土庫鎮",
    "北港鎮",
    "古坑鄉",
    "大埤鄉",
    "莿桐鄉",
    "林內鄉",
    "二崙鄉",
    "崙背鄉",
    "麥寮鄉",
    "東勢鄉",
    "褒忠鄉",
    "臺西鄉",
    "元長鄉",
    "四湖鄉",
    "口湖鄉",
    "水林鄉",
  ],
  嘉義縣: [
    "太保市",
    "朴子市",
    "布袋鎮",
    "大林鎮",
    "民雄鄉",
    "溪口鄉",
    "新港鄉",
    "六腳鄉",
    "東石鄉",
    "義竹鄉",
    "鹿草鄉",
    "水上鄉",
    "中埔鄉",
    "竹崎鄉",
    "梅山鄉",
    "番路鄉",
    "大埔鄉",
    "阿里山鄉",
  ],
  屏東縣: [
    "屏東市",
    "潮州鎮",
    "東港鎮",
    "恆春鎮",
    "萬丹鄉",
    "長治鄉",
    "麟洛鄉",
    "九如鄉",
    "里港鄉",
    "鹽埔鄉",
    "高樹鄉",
    "萬巒鄉",
    "內埔鄉",
    "竹田鄉",
    "新埤鄉",
    "枋寮鄉",
    "新園鄉",
    "崁頂鄉",
    "林邊鄉",
    "南州鄉",
    "佳冬鄉",
    "琉球鄉",
    "車城鄉",
    "滿州鄉",
    "枋山鄉",
    "三地門鄉",
    "霧臺鄉",
    "瑪家鄉",
    "泰武鄉",
    "來義鄉",
    "春日鄉",
    "獅子鄉",
    "牡丹鄉",
  ],
  花蓮縣: [
    "花蓮市",
    "鳳林鎮",
    "玉里鎮",
    "新城鄉",
    "吉安鄉",
    "壽豐鄉",
    "光復鄉",
    "豐濱鄉",
    "瑞穗鄉",
    "富里鄉",
    "秀林鄉",
    "萬榮鄉",
    "卓溪鄉",
  ],
  臺東縣: [
    "臺東市",
    "成功鎮",
    "關山鎮",
    "卑南鄉",
    "鹿野鄉",
    "池上鄉",
    "東河鄉",
    "長濱鄉",
    "太麻里鄉",
    "大武鄉",
    "綠島鄉",
    "海端鄉",
    "延平鄉",
    "金峰鄉",
    "達仁鄉",
    "蘭嶼鄉",
  ],
  金門縣: ["金城鎮", "金沙鎮", "金湖鎮", "金寧鄉", "烈嶼鄉", "烏坵鄉"],
  澎湖縣: ["馬公市", "湖西鄉", "白沙鄉", "西嶼鄉", "望安鄉", "七美鄉"],
  連江縣: ["南竿鄉", "北竿鄉", "莒光鄉", "東引鄉"],
};

const citySuggestions = Object.keys(taiwanAdministrativeAreas);

type MapSearchBarProps = {
  query: string;
  results: MapSearchResponse | null;
  isSearching: boolean;
  error: string | null;
  isFilterOpen: boolean;
  activeFilterCount: number;
  onQueryChange: (query: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  onToggleFilters: () => void;
  onSelectLocation: (location: MapSearchLocation) => void;
  onSelectRestaurant: (restaurant: MapRestaurant) => void;
};

export function MapSearchBar({
  query,
  results,
  isSearching,
  error,
  isFilterOpen,
  activeFilterCount,
  onQueryChange,
  onSubmit,
  onClear,
  onToggleFilters,
  onSelectLocation,
  onSelectRestaurant,
}: MapSearchBarProps) {
  return (
    <div className="map-search-control">
      <form
        className="map-search-bar"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <IconSearch aria-hidden="true" />
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜尋地區、地址或店家名稱"
          aria-label="搜尋地區、地址或店家名稱"
          autoComplete="off"
        />
        {query ? (
          <button
            type="button"
            className="map-search-bar__clear"
            onClick={onClear}
            aria-label="清除搜尋"
          >
            <IconX aria-hidden="true" />
          </button>
        ) : null}
        <button
          type="button"
          className={`map-search-bar__filter${isFilterOpen ? " is-active" : ""}`}
          onClick={onToggleFilters}
          aria-expanded={isFilterOpen}
          aria-controls="map-filter-popover"
          aria-label="篩選"
        >
          <IconAdjustmentsHorizontal aria-hidden="true" />
          <span>篩選</span>
          {activeFilterCount ? <b>{activeFilterCount}</b> : null}
        </button>
      </form>

      {query.trim().length >= 2 ? (
        <MapSearchResults
          results={results}
          isSearching={isSearching}
          error={error}
          onSelectLocation={onSelectLocation}
          onSelectRestaurant={onSelectRestaurant}
        />
      ) : null}
    </div>
  );
}

type MapSearchResultsProps = {
  results: MapSearchResponse | null;
  isSearching: boolean;
  error: string | null;
  onSelectLocation: (location: MapSearchLocation) => void;
  onSelectRestaurant: (restaurant: MapRestaurant) => void;
};

function MapSearchResults({
  results,
  isSearching,
  error,
  onSelectLocation,
  onSelectRestaurant,
}: MapSearchResultsProps) {
  const hasResults = Boolean(results?.locations.length || results?.restaurants.length);

  return (
    <div className="map-search-results" role="listbox" aria-label="搜尋結果">
      {isSearching ? <p className="map-search-results__status">搜尋中…</p> : null}
      {error ? (
        <p className="map-search-results__status is-error" role="alert">
          {error}
        </p>
      ) : null}
      {!isSearching && !error && results && !hasResults ? (
        <p className="map-search-results__status">找不到地區或已發布店家。</p>
      ) : null}

      {!isSearching && !error && results?.locations.length ? (
        <section aria-labelledby="map-search-locations-title">
          <h2 id="map-search-locations-title">地區／地址</h2>
          {results.locations.map((location) => (
            <button
              key={`${location.latitude}:${location.longitude}:${location.label}`}
              type="button"
              role="option"
              aria-selected="false"
              onClick={() => onSelectLocation(location)}
            >
              <IconMapPin aria-hidden="true" />
              <span>
                <strong>{location.label}</strong>
                <small>{location.region ?? "地區／地址"}</small>
              </span>
            </button>
          ))}
        </section>
      ) : null}

      {!isSearching && !error && results?.restaurants.length ? (
        <section aria-labelledby="map-search-restaurants-title">
          <h2 id="map-search-restaurants-title">已發布店家</h2>
          {results.restaurants.map((restaurant) => (
            <button
              key={restaurant.id}
              type="button"
              role="option"
              aria-selected="false"
              onClick={() => onSelectRestaurant(restaurant)}
            >
              <IconToolsKitchen3 aria-hidden="true" />
              <span>
                <strong>{restaurant.name}</strong>
                <small>
                  {restaurant.primary_cuisine.display_name} ·{" "}
                  {priceRangeLabels[restaurant.price_range]}
                </small>
              </span>
            </button>
          ))}
        </section>
      ) : null}
    </div>
  );
}

type MapFilterPopoverProps = {
  filters: MapFilters;
  cuisines: MapCuisine[];
  isLoadingCuisines: boolean;
  onChange: (filters: MapFilters) => void;
  onClear: () => void;
  onApply: () => void;
};

export function MapFilterPopover({
  filters,
  cuisines,
  isLoadingCuisines,
  onChange,
  onClear,
  onApply,
}: MapFilterPopoverProps) {
  const districts = taiwanAdministrativeAreas[filters.city] ?? [];
  const update = (patch: Partial<MapFilters>) => onChange({ ...filters, ...patch });

  function togglePrice(priceRange: MapFilters["priceRanges"][number]) {
    const priceRanges = filters.priceRanges.includes(priceRange)
      ? filters.priceRanges.filter((value) => value !== priceRange)
      : [...filters.priceRanges, priceRange];
    update({ priceRanges });
  }

  function toggleCuisine(cuisineId: string) {
    const cuisineIds = filters.cuisineIds.includes(cuisineId)
      ? filters.cuisineIds.filter((value) => value !== cuisineId)
      : [...filters.cuisineIds, cuisineId];
    update({ cuisineIds });
  }

  return (
    <div id="map-filter-popover" className="map-filter-popover" aria-label="地圖篩選條件">
      <div className="map-filter-popover__fields">
        <fieldset>
          <legend>地區</legend>
          <label>
            縣市
            <select
              value={filters.city}
              onChange={(event) => update({ city: event.target.value, district: "" })}
              aria-label="縣市"
            >
              <option value="">請選擇縣市</option>
              {citySuggestions.map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
            </select>
          </label>
          <label>
            行政區
            <select
              value={filters.district}
              onChange={(event) => update({ district: event.target.value })}
              aria-label="行政區"
              disabled={!filters.city}
            >
              <option value="">{filters.city ? "請選擇行政區" : "請先選擇縣市"}</option>
              {districts.map((district) => (
                <option key={district} value={district}>
                  {district}
                </option>
              ))}
            </select>
          </label>
        </fieldset>

        <fieldset>
          <legend>價格</legend>
          <div className="map-filter-options">
            {Object.entries(priceRangeLabels).map(([value, label]) => (
              <label key={value}>
                <input
                  type="checkbox"
                  checked={filters.priceRanges.includes(value as MapFilters["priceRanges"][number])}
                  onChange={() => togglePrice(value as MapFilters["priceRanges"][number])}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>料理分類</legend>
          {isLoadingCuisines ? <p className="map-filter-hint">正在載入料理分類…</p> : null}
          {!isLoadingCuisines && !cuisines.length ? (
            <p className="map-filter-hint">目前沒有可用的料理分類。</p>
          ) : null}
          <div className="map-filter-options">
            {cuisines.map((cuisine) => (
              <label key={cuisine.id}>
                <input
                  type="checkbox"
                  checked={filters.cuisineIds.includes(cuisine.id)}
                  onChange={() => toggleCuisine(cuisine.id)}
                />
                <span>
                  <i style={{ backgroundColor: cuisine.color }} aria-hidden="true" />
                  {cuisine.display_name}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      </div>

      <div className="map-filter-popover__actions">
        <button type="button" className="button button--quiet" onClick={onClear}>
          清除條件
        </button>
        <button type="button" className="button button--primary" onClick={onApply}>
          套用篩選
        </button>
      </div>
    </div>
  );
}

type MapActiveFilterChipsProps = {
  filters: MapFilters;
  cuisines: MapCuisine[];
  onRemove: (key: "city" | "district" | "priceRange" | "cuisine", value?: string) => void;
};

type FilterChip = {
  key: "city" | "district" | "priceRange" | "cuisine";
  label: string;
  value?: string;
};

export function MapActiveFilterChips({ filters, cuisines, onRemove }: MapActiveFilterChipsProps) {
  const chips: FilterChip[] = [];
  if (filters.city && filters.district) {
    chips.push({ key: "city", label: `${filters.city}・${filters.district}` });
  } else {
    if (filters.city) chips.push({ key: "city", label: filters.city });
    if (filters.district) chips.push({ key: "district", label: filters.district });
  }
  filters.priceRanges.forEach((value) =>
    chips.push({ key: "priceRange", label: priceRangeLabels[value], value }),
  );
  filters.cuisineIds.forEach((value) => {
    const cuisine = cuisines.find((item) => item.id === value);
    chips.push({ key: "cuisine", label: cuisine?.display_name ?? "料理分類", value });
  });

  if (!chips.length) return null;

  return (
    <div className="map-active-filter-chips" aria-label="目前套用的篩選條件">
      {chips.map((chip) => (
        <span key={`${chip.key}:${chip.value ?? chip.label}`}>
          {chip.label}
          <button
            type="button"
            onClick={() => onRemove(chip.key, chip.value)}
            aria-label={`移除條件 ${chip.label}`}
          >
            <IconX aria-hidden="true" />
          </button>
        </span>
      ))}
    </div>
  );
}

export function cloneMapFilters(filters: MapFilters): MapFilters {
  return {
    ...filters,
    cuisineIds: [...filters.cuisineIds],
    priceRanges: [...filters.priceRanges],
  };
}

export function hasMapFilters(filters: MapFilters): boolean {
  return Boolean(
    filters.city || filters.district || filters.cuisineIds.length || filters.priceRanges.length,
  );
}

export function countMapFilters(filters: MapFilters): number {
  return (
    Number(Boolean(filters.city)) +
    Number(Boolean(filters.district)) +
    filters.cuisineIds.length +
    filters.priceRanges.length
  );
}
