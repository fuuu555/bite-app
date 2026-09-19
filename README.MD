# BiteMap

## 技術棧

本技術方案依據 [`FUNCTIONAL_REQUIREMENTS.md`](./FUNCTIONAL_REQUIREMENTS.md) 設計。產品先以響應式 Web 推出，再逐步補齊安裝、推播與離線殼層等 PWA 能力；架構採模組化單體，避免 MVP 階段過早拆分微服務。

### 架構總覽

```text
Browser / Installed PWA
        │
        ├── HTTPS / REST ───────────────┐
        └── WebSocket ──────────────────┤
                                        ▼
                              FastAPI Modular Monolith
                         ┌──────────────┼──────────────┐
                         ▼              ▼              ▼
                 PostgreSQL/PostGIS   Redis       Object Storage
                         ▲          cache/queue/    photos/menu
                         │            pub-sub         images
                         └──────────────┬──────────────┘
                                        ▼
                                  Celery Workers
                         notifications / summaries /
                         trust analysis / image jobs /
                         future area discovery
```

Next.js 只負責 Web／PWA 與必要的前端伺服器渲染，不承擔核心商業規則。FastAPI 是唯一的業務 API，統一處理餐廳、評價、再訪、約飯、投票、聊天、社交關係、封鎖與檢舉規則。

### 核心技術選型

| 層級 | 技術 | 用途與選擇理由 |
|---|---|---|
| Web／PWA | Next.js App Router、React、TypeScript | 建立響應式 Web；後續加入 Manifest、Service Worker、安裝與 Web Push，不需重寫前端 |
| UI | Tailwind CSS、shadcn/ui | 建立一致的元件與設計 Token，同時保留客製化空間 |
| 表單與驗證 | React Hook Form、Zod | 處理登入、留言、約飯與個人資料表單；提供前端即時驗證 |
| 伺服器狀態 | TanStack Query | 管理 API 快取、重新驗證、分頁、樂觀更新與錯誤重試 |
| 輕量前端狀態 | Zustand | 管理篩選條件、建立約飯流程及純 UI 狀態；不複製伺服器資料 |
| 地圖 | Google Maps JavaScript API、Advanced Marker、`@googlemaps/markerclusterer` | 顯示地圖、料理分類標記、店家群聚及群聚縮放 |
| 地址定位 | 可替換的 Geocoding Provider | 管理員輸入地址後取得候選座標；同時保留地圖點選與圖釘拖曳修正能力 |
| API | Python、FastAPI、Pydantic | 實作 REST API、權限與商業規則；亦方便後續加入評論分析與 AI 摘要 |
| ORM／Migration | SQLAlchemy 2、Alembic | 明確管理資料存取、交易與資料庫版本變更 |
| API 合約 | OpenAPI + 產生式 TypeScript Client | 由 FastAPI 規格產生前端型別與 Client，避免前後端欄位不一致 |
| 主資料庫 | PostgreSQL | 儲存使用者、餐廳、留言、再訪、約飯、投票、訊息與社交關係等交易資料 |
| 空間資料 | PostGIS | 儲存餐廳座標、距離篩選、範圍查詢與地圖資料 |
| 快取／即時協調 | Redis | 快取熱門查詢、限流、WebSocket Pub/Sub、背景工作 Broker；不作永久資料來源 |
| 背景工作 | Celery | 執行通知、AI 摘要、評論可信度分析、圖片處理及未來區域資料蒐集等非同步工作 |
| 即時通訊 | FastAPI WebSocket + Redis Pub/Sub | 支援私訊、好友聊天及約飯聊天室；所有訊息仍寫入 PostgreSQL |
| 檔案儲存 | S3 相容 Object Storage | 儲存頭像、留言照片、餐點照片與菜單素材；資料庫只保存中繼資料與物件鍵值 |
| 測試 | Pytest、Vitest、React Testing Library、Playwright | 分別覆蓋後端、前端元件與跨模組核心流程 |
| 開發環境 | Docker Compose、pnpm、uv | 讓 Web、API、Worker、PostgreSQL 與 Redis 可重現地在本機啟動 |
| CI/CD | GitHub Actions、Docker | 執行格式檢查、型別檢查、測試、Migration 檢查與映像建置 |
| 可觀測性 | OpenTelemetry、Sentry、結構化 JSON Log | 追蹤 API、背景工作與前端錯誤，並保留跨服務 Trace ID |

### 前端策略

- 採 Mobile First 響應式設計；桌面 Web 與手機版共用同一套頁面及元件。
- Footer 固定為五個主入口：`探索｜地圖｜約飯｜聊天室｜個人頁面`。
- 先完成一般 Web 能力，再加入 PWA Manifest、Service Worker、安裝提示與 Web Push。
- 餐廳公開資訊可使用 Server Components／SSR；需要登入的聊天、投票及個人操作以 Client Components 與 API 查詢為主。
- 定位功能只在使用者明確同意後啟用；拒絕定位時依序使用上次瀏覽位置與系統預設城市。
- MVP 不將離線編輯與離線訊息列為必要能力；Service Worker 先快取 App Shell 與安全的靜態資源。

### 地圖架構

MVP 採「後端可視範圍查詢＋前端群聚」：

```text
取得目前位置 / 上次位置 / 預設城市
                  ↓
顯示地圖與已載入結果
                  ↓
使用者拖曳或縮放地圖
                  ↓
顯示「搜尋此區域」按鈕
                  ↓
GET /api/v1/map/restaurants
  bounds + cuisine + price
                  ↓
PostGIS 查詢範圍內 published 店家
                  ↓
Marker Clusterer 依縮放層級群聚
                  ↓
群聚標記 ──點擊──> 自動放大並拆群
單店標記 ──點擊──> 底部預覽卡 ──> 餐廳詳細頁
```

- 地圖 API 接收目前可視範圍 `west/south/east/north`、縮放層級、料理分類及價格條件。
- 只有 `published` 店家可以由公開地圖 API 回傳；管理狀態不得依賴前端過濾。
- 餐廳位置使用 PostGIS `geography(Point, 4326)`，並建立 GiST 空間索引。
- MVP 由 API 回傳範圍內的店家點位，瀏覽器使用 `@googlemaps/markerclusterer` 計算畫面群聚。
- 群聚數量在 100 家以下顯示精確值，超過 100 家只改變顯示文字為 `100+`，不可修改實際群聚數量。
- 點擊群聚使用群聚邊界自動放大；放大至單店後，使用 Advanced Marker 顯示店家。
- 單店標記顏色由管理員設定的主要料理分類決定。料理分類需有固定色票，並搭配圖例、圖示或文字，符合無障礙辨識需求。
- 點擊單店標記只開啟底部預覽卡，不立即導頁。預覽卡再連至既有餐廳詳細頁。
- 地圖移動後只標示查詢範圍已改變；直到使用者點擊「搜尋此區域」才送出新請求，避免拖曳時頻繁查詢。
- 查詢期間保留舊結果並顯示載入狀態；請求失敗時保留舊結果、顯示重試操作，不清空整張地圖。
- 若結果超過前端安全上限，API 回傳「請放大地圖」狀態；未來資料量達到監控門檻後，再將群聚計算移至 PostGIS，而不改變使用者操作。

### 店家管理與未來資料蒐集

MVP 由管理員維護正式店家：

- 管理員可輸入地址，透過 Geocoding Provider 取得候選位置。
- 管理員也可直接點擊地圖建立位置；兩種方式產生的圖釘都能拖曳修正。
- 儲存時必須包含標準化地址、座標、主要料理分類、價格區間及發布狀態。
- 一般使用者沒有新增或發布店家的權限。

資料模型應區分正式店家與外部候選資料，避免未審核內容直接進入公開地圖：

```text
restaurant_candidates
  ├── source_provider
  ├── source_external_id
  ├── allowed_source_fields / normalized_fields
  ├── deduplication_key
  └── status: pending / rejected
             │
             └── 管理員核准
                    ↓
restaurants
  ├── location
  ├── primary_cuisine_id
  ├── price_range
  ├── source_kind: manual / imported
  └── status: published / archived
```

未來啟用自動補充店家時，「搜尋此區域」仍先查正式資料庫。若 Coverage Service 判斷該範圍資料不足，只在背景記錄需求並送出 Celery `area_discovery` 工作；使用者不等待外部來源完成。

```text
Area demand
  ↓
Provider Adapter
  ↓
Normalize
  ↓
Deduplicate by provider ID / name / address / coordinates
  ↓
restaurant_candidates (pending)
  ↓
Admin review
  ↓
restaurants (published)
```

外部來源一律經 Provider Adapter 隔離。每個 Provider 必須定義授權、允許保存的欄位、更新週期、來源標示與刪除規則；不可用未授權爬蟲建立永久店家資料庫。Google Places 可作為候選 Provider 研究，但不得假設其回傳內容皆能永久保存，正式使用方式仍需依當時條款確認。

### 後端模組

FastAPI 維持單一部署單元，但程式內按領域隔離：

```text
identity       登入、Session、個人資料與 Tag
restaurants    正式店家、候選店家、菜單、照片與管理審核
discovery      條件篩選、排序與 Top 3
maps           可視範圍查詢、料理標記、資料覆蓋率與區域需求
reviews        留言、再訪、狀態統計、讚與可信度
meals          公開／私人約飯、成員、候選餐廳與投票
chat           私訊、好友聊天、約飯聊天室與訊息權限
social         追蹤、好友、收藏、封鎖與檢舉
notifications  站內通知與 Web Push
```

模組只能透過公開的 Service 介面互動。例如聊天模組向約飯模組確認正式成員資格，而不是直接散落查詢約飯資料表。這可確保「被移除後失去聊天室與投票權限」及「封鎖後跨功能隔離」等規則只有單一實作來源。

### API 與即時資料流

- 一般讀寫使用版本化 REST API，例如 `/api/v1/restaurants`、`/api/v1/meals`。
- 地圖範圍查詢使用 `/api/v1/map/restaurants`；管理員新增與審核使用獨立且受角色保護的管理 API。
- 前端 Client 由 OpenAPI 規格自動產生；CI 檢查產生結果是否與後端同步。
- 聊天與即時狀態使用 WebSocket。建立連線及訂閱聊天室時都要驗證身分與成員資格。
- 訊息先通過後端授權並持久化至 PostgreSQL，再經 Redis Pub/Sub 推送；Redis 中斷不應造成歷史訊息遺失。
- 投票結果、加入／退出與成員移除由資料庫交易保證一致性，不能只依賴前端狀態。
- AI 摘要、可信度分析、圖片處理及大量通知送入 Celery；API 回傳工作狀態，不阻塞一般請求。

### 資料與搜尋策略

- PostgreSQL 是唯一真實資料來源；Redis 僅用於可重建的快取與暫態協調。
- 使用 PostGIS `geography(Point, 4326)` 欄位及 GiST 空間索引處理可視範圍、距離篩選與排序。
- MVP 餐廳名稱搜尋使用 PostgreSQL Full Text Search／`pg_trgm`，暫不導入 Elasticsearch。
- 綜合排序保留可測試的規則層，輸出 Top 3 與完整列表，但不向前端暴露黑箱總分。
- Google 資料與 App 資料分欄、分來源保存，避免合併為單一評分。
- 同一使用者對同一餐廳只保留一個目前狀態供統計；每次再訪另存不可覆蓋的歷史紀錄。
- 評論可信度只輸出「高／普通／偏低」及可公開的異常訊號；權重與門檻仍維持 TBD。

### 身分驗證與安全

- 驗證由 FastAPI 統一管理；Web 使用 Secure、HttpOnly、SameSite Cookie，密碼以 Argon2id 雜湊。
- 所有寫入操作在 API 層驗證身分、資源所有權與目前狀態，不能只依賴前端隱藏按鈕。
- 店家新增、座標修改、主要料理分類設定、候選資料審核與發布都需要管理員角色，並保留操作紀錄。
- 封鎖規則集中為授權 Policy，套用至個人頁、私訊、好友、追蹤、搜尋、推薦與約飯。
- 陌生人首則私訊限制、登入、搜尋與上傳端點使用 Redis 限流。
- 圖片上傳限制 MIME type、檔案大小與像素尺寸，使用簽名 URL 並安排非同步安全處理。
- 檢舉、成員移除、權限變更及管理操作保留稽核紀錄。
- 外部 API Key、Cookie Secret 與資料庫憑證只放在部署平台的 Secret Store，不寫入版本庫。

### 測試重點

- 單元測試：排序、再訪最新票、群聚數字上限、料理顏色映射、平票隨機候選範圍、封鎖 Policy、聊天室與投票資格。
- 整合測試：PostgreSQL 交易、PostGIS 邊界與距離查詢、Redis 限流、Celery 工作、Provider Adapter 及 Object Storage 介面。
- E2E 測試：地圖定位降級、搜尋此區域、篩選、群聚拆分、店家預覽、管理員新增店家、找餐廳、留言與再訪、建立約飯、加入／審核、投票、聊天、退出與封鎖。
- Contract 測試：OpenAPI 產生的 TypeScript Client 必須通過編譯與代表性 API 測試。
- PWA 驗證：Manifest、安裝模式、Service Worker 更新、推播權限與無定位降級流程。

### 部署方式

- `web`：部署為 Next.js Node 應用，可使用支援 Next.js 的平台。
- `api`：以 Docker 容器部署 FastAPI，必須支援長連線 WebSocket。
- `worker`：使用與 API 相同程式映像啟動獨立 Celery Worker，可單獨擴展。
- `postgres`、`redis`、`object storage`：正式環境使用代管服務並啟用備份。
- Web 與 API 採同站台網域或明確的子網域策略，降低 Cookie、CORS 與 PWA Scope 的複雜度。
- 開發、預備與正式環境各自使用獨立資料庫、Redis、儲存空間與外部 API 憑證。

### 建議專案結構

```text
bite/
├── apps/
│   ├── web/                 # Next.js Web / PWA
│   ├── api/                 # FastAPI modular monolith
│   └── worker/              # Celery 啟動與工作設定
├── packages/
│   ├── api-client/          # OpenAPI 產生的 TypeScript Client
│   └── ui/                  # 共用 UI 元件與 design tokens
├── infra/
│   ├── docker/              # Container 設定
│   └── compose.yaml         # 本機相依服務
├── tests/
│   └── e2e/                 # Playwright 跨模組測試
├── FUNCTIONAL_REQUIREMENTS.md
└── README.MD
```

### MVP 邊界

- 不拆微服務；先以清楚的領域模組維持邊界。
- 不導入 Elasticsearch、Kafka、Kubernetes 或機器學習推薦系統。
- MVP 店家由管理員新增；不啟用即時爬蟲、背景區域蒐集或未審核資料自動發布。
- MVP 使用前端 Marker Clusterer；資料量未達監控門檻前不實作伺服器端群聚或向量圖磚。
- 評論可信度先採可解釋的規則與人工可驗證訊號，不自行決定需求文件中的權重與門檻。
- 外部店家、Google 餐廳與評論資料的正式來源及授權方式尚未決定，實作時以 Provider Adapter 隔離。
- 個人美食地圖的收錄規則、私人約飯條件、同飯局封鎖處理等既有 TBD，仍需產品決策後才能實作。
