# Stage 6 留言、再訪與收藏設計

## Design Read

BiteMap 的餐廳頁是暖色、地圖優先的內容型 App；本階段延續既有 `Friendly City Map` 視覺語言，以清楚的留言閱讀、低摩擦的再訪紀錄與可回到個人頁的收藏為核心。介面採已確認的「分頁集中操作」方向，保留手機優先、可掃讀與完整 loading／empty／error／success 狀態。

## 目標與範圍

Stage 6 先完成餐廳內容的基本閉環：

- 已登入一般使用者可以在已發布餐廳留下必填文字與三段式再訪狀態。
- 同一使用者對同一家餐廳只有一條留言串；第一次建立原始留言 entry，再次到訪時在同一 thread 下新增 entry，不建立獨立頂層評論。
- 統計只取每位使用者仍有效的最新紀錄，因此每位使用者在統計中只佔一票。
- 使用者可以修改或軟刪除自己的留言；修改顯示「已編輯」，刪除前顯示確認提示，刪除後不出現在公開留言列表。
- 使用者可以對留言按讚、切換留言排序／狀態篩選，並收藏餐廳。
- 個人頁可以查看自己的收藏餐廳。

本階段暫不實作：

- S3 相容 Object Storage、簽名上傳、圖片驗證與留言照片 UI。文字／再訪／收藏基本流程完成後才做。
- 管理員隱藏留言、公開頁隱藏提示、管理後台留言管理 API 與 UI。這列為 Stage 6 後續未完成項目；實際產品目前不顯示內部規劃標註。
- 評論可信度演算法、AI 摘要、反作弊與到店驗證。這些維持 `TBD`，不在本階段自行定義。

## 方案比較與決定

### 方案 A：一筆使用者餐廳資料，更新原列

用一張表保存每位使用者對每間餐廳的目前留言與狀態，更新時覆蓋原內容。實作最簡單，但無法保留完整再訪時間線，也不符合已確認的稽核與歷史需求。

### 方案 B：留言串與 entry 追加，統計讀取最新有效 entry（採用）

每位使用者與餐廳先建立唯一 `restaurant_review_threads`，第一次留言與後續再訪都在 `restaurant_reviews` 新增 entry，並以 `thread_id` 與 `entry_number` 保持明確父子關係。編輯只修改該 entry 並更新 `updated_at`；刪除使用 `deleted_at` 軟刪除。統計查詢每條 thread 最新的未刪除 entry，公開列表排除已刪除 entry，但展開時間線時保留已刪除位置並標示狀態。此方案同時保留時間線、支援刪除後重新計算統計，也讓未來管理稽核有穩定資料基礎。

### 方案 C：事件表加目前狀態快照表

除完整事件表外，再維護一張每位使用者的目前狀態快照表，以較快地讀取統計。現階段資料量小且尚未有快取需求，會增加交易同步與修復成本，因此保留作為日後效能優化，不納入 MVP。

## 資料模型

### `restaurant_review_threads`

一列代表一位使用者對一家餐廳的唯一留言串，`(restaurant_id, user_id)` 具唯一限制。它是原始留言與所有再訪 entry 的父層。

### `restaurant_reviews`

一列代表留言串中的一次原始留言／再訪 entry。資料保持關聯式欄位，不使用 JSON 儲存可查詢的狀態。

- `id`：UUID 主鍵。
- `thread_id`：外鍵至 `restaurant_review_threads`；所有再訪 entry 都掛在同一條 thread。
- `entry_number`：thread 內從 1 開始的順序；1 代表原始留言，大於 1 代表再訪。
- `restaurant_id`：外鍵至 `restaurants`，索引；只允許已發布餐廳在公開 API 建立內容。
- `user_id`：外鍵至 `users`，索引。
- `content`：必填文字，後端限制長度並去除前後空白。
- `revisit_status`：`will_return`、`neutral`、`will_not_return` 三值限制。
- `created_at`：事件建立時間；再訪事件依此形成時間線。
- `updated_at`：編輯時更新，原始 `created_at` 保留。
- `deleted_at`：nullable；使用者刪除時設定，不做 hard delete。

同一使用者與餐廳的唯一限制放在 thread；entry 本身不設單列唯一限制，以容納完整再訪歷史。公開列表預設 `deleted_at IS NULL`，時間線則保留已刪除 entry 的位置並標示「已刪除」。

### `review_reasons` 與 `restaurant_review_reasons`

原因標籤採獨立字典與關聯表，避免在留言中寫入 JSON。初始標籤由程式種子資料建立，保留擴充欄位但不開放一般使用者自行建立系統原因。

### `review_likes`

保存使用者對留言的按讚關係，使用 `(review_id, user_id)` 複合唯一限制避免重複按讚。已刪除留言不提供公開按讚操作；既有按讚資料不因留言軟刪除而破壞。

### `restaurant_favorites`

保存使用者與餐廳的收藏關係，使用 `(restaurant_id, user_id)` 複合主鍵或唯一限制。重複收藏採冪等成功，取消收藏為刪除關係資料；收藏不影響探索排序。

### 統計規則

對指定餐廳，先從未刪除的 `restaurant_reviews` 依 `user_id` 分組，取 `created_at DESC, id DESC` 的第一筆，再計算：

- `rating_count`：仍有有效最新紀錄的使用者人數。
- `will_return_count`、`neutral_count`、`will_not_return_count`：各狀態人數。
- `revisit_rate`：`will_return_count / rating_count * 100`；沒有有效紀錄時回傳 `null`。

刪除某位使用者的最新紀錄後，如果該使用者仍有較早的未刪除紀錄，統計回到那筆紀錄；如果沒有，該使用者不再計入統計。這與公開列表排除被刪除事件的規則一致。

## API 與授權

所有一般使用者 API 沿用現有 User Session cookie 與後端 `User.role == "user"` 授權。管理員仍使用現有獨立 `/admin/login` 和 `AdminSession`，本階段不新增管理留言 API。

### 公開／登入後餐廳內容

- `GET /api/v1/explore/restaurants/{restaurant_id}`：擴充既有 `app` 統計欄位，回傳目前有效最新狀態的統計。
- `GET /api/v1/explore/restaurants/{restaurant_id}/reviews`：回傳公開留言，支援 `sort=featured|latest|popular` 與 `status=all|will_return|neutral|will_not_return`；游標或分頁欄位依現有 API 慣例實作。
- `POST /api/v1/explore/restaurants/{restaurant_id}/reviews`：登入使用者建立留言事件，文字、狀態必填，原因可選。
- `PATCH /api/v1/reviews/{review_id}`：只允許留言作者修改自己的內容、狀態與原因；保留 `created_at` 並更新 `updated_at`。
- `DELETE /api/v1/reviews/{review_id}`：只允許留言作者設定 `deleted_at`；回傳成功後該留言從公開列表消失。
- `POST /api/v1/reviews/{review_id}/like` 與 `DELETE /api/v1/reviews/{review_id}/like`：登入使用者冪等按讚／取消按讚。

### 收藏

- `GET /api/v1/users/me/favorites`：回傳目前登入使用者的收藏餐廳，使用分頁。
- `POST /api/v1/restaurants/{restaurant_id}/favorite`：新增收藏，重複請求保持成功。
- `DELETE /api/v1/restaurants/{restaurant_id}/favorite`：取消收藏。

所有修改端點都在 Service 層重新查詢使用者與資源關係，不依賴前端隱藏控制項。未登入回傳 401、資源不存在回傳 404、非作者修改／刪除回傳 403、欄位不合法回傳 422；錯誤訊息不洩漏其他使用者的私有資料。

## 前端流程

餐廳詳情頁延續目前主內容，新增集中操作區：

1. 餐廳摘要下方顯示 App 統計：樣本數、三種狀態比例與再訪率；無資料時使用既有安全空狀態。
2. 分頁切換「留言」、「再訪紀錄」與目前使用者的收藏操作；頁籤不改變餐廳主摘要與地圖導覽。
3. 留言頁提供排序與狀態篩選，預設綜合排序；卡片顯示作者、內容、狀態、再訪次數、建立時間／更新時間、按讚數。
4. 作者自己的留言提供編輯入口；編輯表單沿用建立表單並顯示目前狀態與原因。
5. 作者按刪除時先顯示確認提示；確認後送出軟刪除，成功後從公開清單移除並重新抓取統計與留言。
6. 編輯成功後在列表顯示「已編輯」，不顯示內部 deleted_at 或管理流程欄位。
7. 收藏按鈕提供明確的 active、loading、失敗可重試狀態；個人頁收藏列表使用與探索列表一致的餐廳摘要元件。

頁面必須包含 loading、empty、error、retry、disabled、focus-visible 與成功回饋狀態；動態效果只用於操作完成的短回饋，不依賴動畫傳達重要資訊，並支援 `prefers-reduced-motion`。不使用假照片、漸層或新增與既有品牌不一致的色彩。

## 錯誤與一致性

- 建立、編輯、刪除、按讚與收藏操作使用 TanStack Query 的重新驗證或等價的現有資料抓取策略，避免本地快取與統計不一致。
- 後端交易在寫入事件、原因關聯與統計可見狀態時保持原子性；資料庫唯一限制作為最後一道重複防護。
- 刪除只標記 `deleted_at`，不刪除留言事件、再訪時間線或稽核可追溯資料。
- API 不接受前端傳入的 `user_id`、作者或統計欄位；這些欄位由 Session 與資料庫查詢決定。
- 圖片欄位與 Object Storage URL 不在基本留言 API 中先行佔位，避免未完成的儲存策略滲入產品流程。

## 測試策略與驗收

### 後端

- migration upgrade／downgrade 可逆。
- 建立留言必須要求文字與三段式狀態；原因為可選且只接受有效標籤。
- 同一使用者多次再訪會在同一 thread 保留多列 entry，統計只計最新未刪除 entry；同一使用者同一家店不能建立第二條 thread。
- 編輯保留 `created_at`、更新 `updated_at`，公開回應帶 `is_edited` 或可由時間欄位穩定判定。
- 軟刪除後公開列表排除 entry，時間線保留已刪除位置；刪除最新 entry 時統計正確回退到上一筆有效 entry。
- 非作者無法編輯／刪除；重複按讚與重複收藏不會產生重複關係。
- 收藏列表只回傳目前登入者的資料，已封存餐廳不進入公開內容。
- OpenAPI schema 與產生的前端型別同步。

### 前端與 E2E

- 留言表單驗證、狀態與原因選擇、編輯成功的「已編輯」、刪除確認與成功移除。
- 留言排序／狀態篩選、按讚 loading／錯誤回復、收藏切換與個人收藏空狀態。
- 未登入操作導向登入頁；API 401、403、404、422 顯示可理解且可恢復的 UI。
- 手機與桌面版檢查頁籤、表單、留言卡片與 footer 不互相遮擋，鍵盤可完成主要流程。

## 後續未完成項目

Stage 6 基本內容驗收後，再依序補上：

1. S3 相容圖片儲存、簽名上傳、MIME／大小／像素驗證、失敗重試與留言照片 UI。
2. 管理員隱藏：沿用現有 `User.role == "admin"` 與 `AdminSession`，新增後端管理 API、操作稽核欄位與管理後台；公開頁再顯示「已被管理員隱藏」的產品文案。此項目在基本留言流程完成前不實作。
3. 評論可信度、反作弊與到店驗證，等待產品決策後另行設計。
