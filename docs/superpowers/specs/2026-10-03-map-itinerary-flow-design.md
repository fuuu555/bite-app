# 地圖加入行程與正式行程頁設計

日期：2026-10-03  
狀態：已由使用者確認設計，待實作

## 目標

把地圖頁上的餐廳、景點與住宿探索串成可操作的旅客流程：使用者可以從地圖預覽卡加入地點，進入獨立的「我的行程」頁檢視與排序，最後在 BiteMap 內部地圖顯示行程順序線路。

本批先使用瀏覽器 `localStorage` 保存，讓功能不依賴新資料庫或外部 API Key；同時抽出 storage adapter，保留未來替換成帳號同步 API 的邊界。

## 需求規則差異

現有 `FUNCTIONAL_REQUIREMENTS.md` 只定義公開地圖顯示 BiteMap 店家與交通部觀光署開放資料。本功能新增以下已確認行為：

- 地圖預覽卡支援餐廳、景點、旅館民宿加入行程。
- 地圖頁顯示目前行程摘要與地點數量。
- 新增 `/itinerary` 獨立行程管理頁。
- 行程使用瀏覽器本機保存，重新整理後仍保留。
- 行程可排序、移除、清空與在 BiteMap 內部地圖顯示順序線路。
- 正式版預留後端帳號同步替換，不在本批新增資料庫模型。

## 使用者流程

### 地圖頁

1. 使用者搜尋或點擊地圖上的餐廳、景點、住宿。
2. 預覽卡顯示「加入行程」。
3. 點擊後立即寫入本機行程，按鈕變為「已加入」。
4. 重複點擊不產生重複地點。
5. 地圖頁顯示行程摘要面板；桌面版為側欄或浮動面板，手機版為底部摘要列。
6. 點擊「查看完整行程」前往 `/itinerary`。

### 我的行程頁

1. 顯示吃飯、景點、住宿等已選地點。
2. 每個項目顯示來源、類型、名稱、地址與座標狀態。
3. 支援上移、下移與移除；行程順序同步保存。
4. 支援清空全部行程，使用 App 內確認框避免誤刪。
5. 有至少一個具座標地點時顯示「顯示內部路線」。
6. 點擊後，在 MapLibre 地圖上以行程順序顯示地點連線。
7. 缺少座標的項目仍可保留，但顯示無法加入路線的原因；其他具座標地點仍可顯示線路。

## 資料與 function 邊界

### 本機 storage adapter

使用版本化 key，例如 `bitemap-itinerary-v1`：

```ts
type SavedItinerary = {
  version: 1;
  updatedAt: string;
  places: SavedItineraryPlace[];
};
```

必要 function：

- `readSavedItinerary()`：讀取、解析、版本與欄位驗證；損壞時回傳空行程。
- `writeSavedItinerary()`：寫入更新時間與版本。
- `addItineraryPlace()`：依 `source + id` 去重。
- `removeItineraryPlace()`：移除指定地點。
- `moveItineraryPlace()`：調整排序並限制索引範圍。
- `clearItinerary()`：清除全部地點。
- `isPlaceInItinerary()`：供按鈕狀態使用。
- `getItineraryCategoryLabel()`：統一顯示吃飯、景點、住宿等類型。
- `buildItineraryRouteLine()`：依順序產生內部地圖線路座標，只納入具有效座標的地點。
- `buildGoogleMapsDirectionsUrl()`：保留給未來外部導航整合，不是本批 UI 主流程。

`SavedItineraryPlace` 只保存行程頁需要的穩定欄位：來源、資料集、來源紀錄 ID、類型、名稱、地址、緯度、經度、官方網址與資料更新時間。不得保存秘密、Token 或外部服務憑證。

### 正式版替換策略

正式帳號同步版預留 `ItineraryStorage` 介面：

```ts
interface ItineraryStorage {
  load(): Promise<SavedItinerary>;
  save(itinerary: SavedItinerary): Promise<void>;
  clear(): Promise<void>;
}
```

本批使用 `LocalStorageItineraryStorage`。正式替換時新增 `ApiItineraryStorage`，由後端提供目前登入使用者的行程讀取、建立、排序、刪除與清空 API；地圖頁與行程頁只依賴介面，不直接依賴 `localStorage`。正式同步資料須使用關聯式資料表保存行程與行程地點，不以單一 JSON 欄位取代關聯資料，並需新增可逆 Alembic migration、後端權限檢查與 OpenAPI client 型別。

正式替換的同步策略：登入後先讀取伺服器行程；若本機仍有未同步資料，顯示合併確認，依 `source + source_record_id` 去重，保留使用者確認的順序後再上傳。API 失敗時保留本機資料並顯示可重試狀態。

## 內部地圖路線預覽與外部導航

- 我的導航第一版指 BiteMap 內部 MapLibre 地圖的順序線路預覽，不跳出 Google Maps。
- 線路依使用者排序連接具有效座標的地點，並自動縮放至行程範圍。
- 目前位置只作為地圖中心參考，不寫入 URL 或 `localStorage`。
- 線路是視覺化順序預覽，不代表真實道路幾何、行車時間或最佳路徑。
- 真實道路 Routing API、即時交通與外部 Google Maps 多站導航列為後續功能，屆時重新確認授權與 API Key。

## 錯誤與狀態

- `localStorage` 不可用或容量不足：維持頁面操作，顯示「本次變更未保存」提示。
- 本機資料 JSON 損壞或版本不支援：清除無法解析的本機資料並回復空行程。
- API 回傳資料缺少座標：可保存、不可納入導航，清楚標示原因。
- 行程為空：顯示空狀態與返回地圖入口。
- 導航地點不足：禁用導航按鈕並說明至少需要一個可導航地點。

## 測試與驗收

### 單元測試

- 讀寫、版本驗證、損壞資料 fallback。
- 新增去重、移除、排序、清空。
- 內部路線顯示、排序順序與缺少座標情況。

### 元件／整合測試

- 地圖預覽卡加入後顯示已加入。
- 地圖摘要數量與本機資料同步。
- 行程頁重新整理後保留資料。
- 移除與排序後重新整理仍維持狀態。

### E2E

- 地圖點選餐廳／觀光資料 → 加入行程 → 前往行程頁。
- 行程頁排序、移除、清空與空狀態。
- 「顯示內部路線」按鈕會在地圖上顯示順序線路，不依賴 Google 外部頁面內容。
- 桌面與手機寬度均可操作。

## 不在本批範圍

- 後端永久保存、跨裝置同步與行程分享。
- 真正的道路路線 polyline、即時交通與碳排計算。
- Routing API Key 或 Google Places 資料匯入。
- 自動預訂餐廳、住宿或付款。
