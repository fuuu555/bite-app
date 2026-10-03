"use client";

import {
  IconArrowRight,
  IconCurrentLocation,
  IconMapPin,
  IconPlus,
  IconRefresh,
  IconRoute,
  IconSparkles,
  IconToolsKitchen3,
} from "@tabler/icons-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import {
  fetchItineraryPlan,
  type ItineraryDuration,
  type ItineraryPlan,
  type ItineraryPlanRequest,
  type ItineraryPlace,
  type ItineraryQuickAction,
  type ItineraryStop,
  type ItineraryTransport,
} from "@/features/itinerary/api/itinerary-api";
import { ItineraryMap } from "@/features/itinerary/components/itinerary-map";
import {
  addItineraryPlace,
  isPlaceInItinerary,
  readSavedItinerary,
  removeItineraryPlace,
  toPlannedItineraryPlace,
  writeSavedItinerary,
  type SavedItinerary,
} from "@/features/itinerary/lib/itinerary-storage";

type LocationState = { latitude: number; longitude: number } | null;

const cityOptions = [
  "台北市",
  "新北市",
  "桃園市",
  "台中市",
  "台南市",
  "高雄市",
  "基隆市",
  "新竹市",
  "嘉義市",
  "宜蘭縣",
  "花蓮縣",
  "台東縣",
  "屏東縣",
  "南投縣",
];

const quickActions: Array<{
  action: ItineraryQuickAction;
  label: string;
  description: string;
}> = [
  { action: "eat", label: "想吃飯", description: "附近餐廳與觀光署餐飲" },
  { action: "stay", label: "找住宿", description: "只推薦觀光署旅館民宿" },
  { action: "attraction", label: "找景點", description: "附近景點與旅遊節點" },
  { action: "plan", label: "規劃行程", description: "景點、吃飯與住宿組合" },
];

const interestOptions = ["自然", "文化", "美食", "親子"];
const roleLabels: Record<ItineraryStop["role"], string> = {
  attraction: "景點",
  meal: "吃飯",
  lodging: "住宿",
  service_site: "服務站",
};
const datasetLabels: Record<ItineraryPlace["source_dataset"], string> = {
  bitemap: "BiteMap 已發布店家",
  food: "觀光署餐飲資料",
  attraction: "觀光署景點資料",
  hotel: "觀光署旅館民宿資料",
  service_site: "觀光署旅遊服務站",
};

function distanceLabel(meters: number) {
  return meters < 1000
    ? `${Math.max(1, Math.round(meters))} 公尺`
    : `${(meters / 1000).toFixed(1)} 公里`;
}

function stopKey(place: ItineraryPlace) {
  return `${place.source}-${place.id}`;
}

function PlaceSource({ place }: { place: ItineraryPlace }) {
  return <span className="itinerary-place__source">{datasetLabels[place.source_dataset]}</span>;
}

function PlaceCard({
  place,
  actionLabel = "加入行程",
  isAdded = false,
  onAction,
}: {
  place: ItineraryPlace;
  actionLabel?: string;
  isAdded?: boolean;
  onAction?: () => void;
}) {
  return (
    <article className="itinerary-place">
      <div
        className="itinerary-place__icon"
        style={{ backgroundColor: `${place.icon_color}22`, color: place.icon_color }}
      >
        {place.category === "restaurant" ? (
          <IconToolsKitchen3 aria-hidden="true" />
        ) : (
          <IconMapPin aria-hidden="true" />
        )}
      </div>
      <div className="itinerary-place__body">
        <PlaceSource place={place} />
        <h3>{place.name}</h3>
        <p>{place.address ?? "官方資料未提供地址"}</p>
        <div className="itinerary-place__meta">
          <span>{distanceLabel(place.distance_meters)}</span>
          {place.cuisine_name ? <span>{place.cuisine_name}</span> : null}
        </div>
      </div>
      {onAction ? (
        <button
          className="button button--quiet itinerary-place__action"
          type="button"
          onClick={onAction}
          disabled={isAdded}
        >
          {isAdded ? <IconMapPin aria-hidden="true" /> : <IconPlus aria-hidden="true" />}
          {isAdded ? "已加入行程" : actionLabel}
        </button>
      ) : null}
    </article>
  );
}

function StopCard({
  stop,
  isAdded,
  onAdd,
}: {
  stop: ItineraryStop;
  isAdded: boolean;
  onAdd: () => void;
}) {
  return (
    <article className="itinerary-stop">
      <div className="itinerary-stop__number" aria-hidden="true">
        {stop.order}
      </div>
      <div className="itinerary-stop__content">
        <div className="itinerary-stop__eyebrow">
          <span>{roleLabels[stop.role]}</span>
          <span>{stop.suggested_duration_minutes} 分鐘</span>
        </div>
        <h3>{stop.place.name}</h3>
        <p>{stop.reason}</p>
        <PlaceSource place={stop.place} />
        <button className="button button--quiet" type="button" onClick={onAdd} disabled={isAdded}>
          {isAdded ? <IconMapPin aria-hidden="true" /> : <IconPlus aria-hidden="true" />}
          {isAdded ? "已加入行程" : "加入我的行程"}
        </button>
      </div>
    </article>
  );
}

export function ItineraryPage() {
  const [location, setLocation] = useState<LocationState>(null);
  const [locationMessage, setLocationMessage] = useState("尚未取得目前位置，可直接選擇縣市。");
  const [city, setCity] = useState("台北市");
  const [quickAction, setQuickAction] = useState<ItineraryQuickAction>("plan");
  const [duration, setDuration] = useState<ItineraryDuration>("half_day");
  const [radiusKm, setRadiusKm] = useState<2 | 5 | 10>(5);
  const [transport, setTransport] = useState<ItineraryTransport>("public_transport");
  const [interests, setInterests] = useState<string[]>(["自然"]);
  const [mealPreference, setMealPreference] = useState("");
  const [includeLodging, setIncludeLodging] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [plan, setPlan] = useState<ItineraryPlan | null>(null);
  const [savedItinerary, setSavedItinerary] = useState<SavedItinerary>({
    version: 1,
    updatedAt: new Date(0).toISOString(),
    places: [],
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setSavedItinerary(readSavedItinerary()));
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        ({ coords }) => {
          setLocation({ latitude: coords.latitude, longitude: coords.longitude });
          setLocationMessage("已使用目前位置推薦附近旅遊地點。");
        },
        () => setLocationMessage("定位未開啟，已保留縣市選擇。"),
        { enableHighAccuracy: false, maximumAge: 300_000, timeout: 8_000 },
      );
    }
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function locate() {
    if (!navigator.geolocation) {
      setLocationMessage("此瀏覽器不支援定位，請選擇縣市。");
      return;
    }
    setLocationMessage("正在取得目前位置…");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocation({ latitude: coords.latitude, longitude: coords.longitude });
        setLocationMessage("已使用目前位置推薦附近旅遊地點。");
      },
      () => {
        setLocation(null);
        setLocationMessage("無法取得位置，請選擇縣市後繼續。");
      },
      { enableHighAccuracy: false, maximumAge: 300_000, timeout: 8_000 },
    );
  }

  function toggleInterest(value: string) {
    setInterests((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value].slice(0, 5),
    );
  }

  async function submit(event?: FormEvent<HTMLFormElement>, action = quickAction) {
    event?.preventDefault();
    setIsLoading(true);
    setError(null);
    const payload: ItineraryPlanRequest = {
      ...(location ? { latitude: location.latitude, longitude: location.longitude } : { city }),
      quick_action: action,
      duration,
      radius_km: radiusKm,
      transport,
      interests,
      meal_preference: mealPreference || undefined,
      include_lodging: includeLodging,
      prompt: prompt.trim() || undefined,
    };
    try {
      setPlan(await fetchItineraryPlan(payload));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "行程推薦暫時無法使用。");
    } finally {
      setIsLoading(false);
    }
  }

  function runQuickAction(action: ItineraryQuickAction) {
    setQuickAction(action);
    void submit(undefined, action);
  }

  function addStop(place: ItineraryPlace) {
    const savedPlace = toPlannedItineraryPlace(place);
    if (isPlaceInItinerary(savedItinerary, savedPlace)) return;
    const next = addItineraryPlace(savedItinerary, savedPlace);
    setSavedItinerary(next);
    if (!writeSavedItinerary(next)) {
      setError("地點已加入目前行程，但本次變更未保存。請稍後重試。");
    }
  }

  const mapStops = plan?.stops ?? [];
  const mapLatitude = plan?.center_latitude ?? location?.latitude;
  const mapLongitude = plan?.center_longitude ?? location?.longitude;

  return (
    <main className="itinerary-page">
      <section className="itinerary-hero">
        <div className="itinerary-hero__copy">
          <div className="itinerary-eyebrow">
            <IconSparkles aria-hidden="true" />
            AI 個人化旅遊
          </div>
          <h1>從現在的位置，開始一段剛剛好的旅程。</h1>
          <p>全台觀光署資料與 BiteMap 店家一起規劃，推薦的每個地點都能追溯來源。</p>
        </div>
        <div className="itinerary-hero__mark" aria-hidden="true">
          <IconRoute />
        </div>
      </section>

      <section className="itinerary-workspace" aria-label="AI 旅遊規劃">
        <div className="itinerary-controls">
          <div className="itinerary-location-row">
            <div>
              <span className="itinerary-label">搜尋中心</span>
              <strong>{location ? "目前位置" : city}</strong>
              <small>{locationMessage}</small>
            </div>
            <button className="button button--secondary" type="button" onClick={locate}>
              <IconCurrentLocation aria-hidden="true" />
              使用目前位置
            </button>
          </div>

          {!location ? (
            <label className="itinerary-field">
              <span>選擇縣市</span>
              <select value={city} onChange={(event) => setCity(event.target.value)}>
                {cityOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div className="itinerary-quick-actions" aria-label="旅遊快捷功能">
            {quickActions.map((item) => (
              <button
                key={item.action}
                className={`itinerary-quick-action${quickAction === item.action ? " is-active" : ""}`}
                type="button"
                onClick={() => runQuickAction(item.action)}
              >
                <strong>{item.label}</strong>
                <span>{item.description}</span>
              </button>
            ))}
          </div>

          <form className="itinerary-form" onSubmit={submit}>
            <label className="itinerary-field itinerary-field--wide">
              <span>用一句話告訴我你想去哪裡</span>
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="例如：我在花蓮，明天想安排自然景點，中午吃素，晚上住附近，不開車"
                rows={3}
              />
            </label>
            <div className="itinerary-form__grid">
              <label className="itinerary-field">
                <span>行程時間</span>
                <select
                  value={duration}
                  onChange={(event) => setDuration(event.target.value as ItineraryDuration)}
                >
                  <option value="half_day">半日</option>
                  <option value="full_day">一日</option>
                </select>
              </label>
              <label className="itinerary-field">
                <span>搜尋距離</span>
                <select
                  value={radiusKm}
                  onChange={(event) => setRadiusKm(Number(event.target.value) as 2 | 5 | 10)}
                >
                  <option value={2}>2 公里內</option>
                  <option value={5}>5 公里內</option>
                  <option value={10}>10 公里內</option>
                </select>
              </label>
              <label className="itinerary-field">
                <span>交通方式</span>
                <select
                  value={transport}
                  onChange={(event) => setTransport(event.target.value as ItineraryTransport)}
                >
                  <option value="public_transport">大眾運輸</option>
                  <option value="walking">步行優先</option>
                  <option value="driving">自駕</option>
                </select>
              </label>
            </div>
            <fieldset className="itinerary-options">
              <legend>興趣偏好</legend>
              <div>
                {interestOptions.map((option) => (
                  <label key={option} className="itinerary-check">
                    <input
                      type="checkbox"
                      checked={interests.includes(option)}
                      onChange={() => toggleInterest(option)}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="itinerary-form__bottom">
              <label className="itinerary-field itinerary-field--meal">
                <span>飲食偏好（可選）</span>
                <input
                  type="text"
                  value={mealPreference}
                  onChange={(event) => setMealPreference(event.target.value)}
                  placeholder="例如：素食、海鮮"
                />
              </label>
              <label className="itinerary-check itinerary-check--lodging">
                <input
                  type="checkbox"
                  checked={includeLodging}
                  onChange={(event) => setIncludeLodging(event.target.checked)}
                />
                <span>需要安排住宿（只使用 7780）</span>
              </label>
              <button className="button button--primary" type="submit" disabled={isLoading}>
                <IconSparkles aria-hidden="true" />
                {isLoading ? "正在規劃…" : "開始規劃"}
              </button>
            </div>
          </form>
          {error ? <p className="itinerary-message is-error">{error}</p> : null}
        </div>

        <div className="itinerary-results">
          {plan && mapLatitude !== undefined && mapLongitude !== undefined ? (
            <ItineraryMap latitude={mapLatitude} longitude={mapLongitude} stops={mapStops} />
          ) : (
            <div className="itinerary-results__empty">
              <IconRoute aria-hidden="true" />
              <strong>你的行程地圖會出現在這裡</strong>
              <span>先選一個快捷功能，或輸入你想要的旅遊方式。</span>
            </div>
          )}
          {plan ? (
            <div className="itinerary-results__panel">
              <div className="itinerary-results__heading">
                <div>
                  <span className="itinerary-eyebrow">
                    {plan.source === "ai" ? "AI 解析" : "智慧推薦"}
                  </span>
                  <h2>{plan.title}</h2>
                  <p>{plan.summary}</p>
                </div>
                <button
                  className="button button--quiet"
                  type="button"
                  onClick={() => void submit()}
                >
                  <IconRefresh aria-hidden="true" />
                  重新推薦
                </button>
              </div>
              <div className="itinerary-stops">
                {plan.stops.length ? (
                  plan.stops.map((stop) => (
                    <StopCard
                      key={`${stop.order}-${stopKey(stop.place)}`}
                      stop={stop}
                      isAdded={isPlaceInItinerary(
                        savedItinerary,
                        toPlannedItineraryPlace(stop.place),
                      )}
                      onAdd={() => addStop(stop.place)}
                    />
                  ))
                ) : (
                  <div className="itinerary-results__empty is-inline">
                    <strong>目前沒有符合條件的地點</strong>
                    <span>請放大搜尋距離，或換一個縣市／興趣。</span>
                  </div>
                )}
              </div>
              {plan.alternatives.length ? (
                <section
                  className="itinerary-alternatives"
                  aria-labelledby="itinerary-alternatives-title"
                >
                  <div className="itinerary-section-heading">
                    <h3 id="itinerary-alternatives-title">可以替換的地點</h3>
                    <span>{plan.alternatives.length} 個選項</span>
                  </div>
                  {plan.alternatives.slice(0, 4).map((place) => (
                    <PlaceCard
                      key={stopKey(place)}
                      place={place}
                      isAdded={isPlaceInItinerary(savedItinerary, toPlannedItineraryPlace(place))}
                      onAction={() => addStop(place)}
                    />
                  ))}
                </section>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>

      {savedItinerary.places.length ? (
        <section className="itinerary-saved" aria-labelledby="itinerary-saved-title">
          <div>
            <span className="itinerary-eyebrow">我的行程草稿</span>
            <h2 id="itinerary-saved-title">已加入 {savedItinerary.places.length} 個地點</h2>
          </div>
          <div className="itinerary-saved__list">
            {savedItinerary.places.map((place) => (
              <span key={`${place.source}-${place.source_record_id}`}>
                {place.name}
                <button
                  type="button"
                  aria-label={`移除 ${place.name}`}
                  onClick={() => {
                    const next = removeItineraryPlace(savedItinerary, place);
                    setSavedItinerary(next);
                    if (!writeSavedItinerary(next)) {
                      setError("地點已從目前行程移除，但本次變更未保存。請稍後重試。");
                    }
                  }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <span className="itinerary-saved__hint">
            <IconArrowRight aria-hidden="true" /> 已保存於本機；
            <Link href="/itinerary">前往我的行程管理與導航</Link>
          </span>
        </section>
      ) : null}
    </main>
  );
}
