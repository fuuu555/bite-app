# BiteMap

開發規則請參考 [`RULE.md`](./RULE.md)。任何偏離或新增 `FUNCTIONAL_REQUIREMENTS.md`／`DEVELOPMENT_PLAN.md` 的功能，都會先確認後再實作並同步文件。

## QUICK START

### 1. 取得專案

```powershell
git clone https://github.com/fuuu555/bite-app.git

```

### 2. 安裝開發工具

Windows 11 可直接使用 `winget`：

```powershell
winget install --id OpenJS.NodeJS.LTS --exact
winget install --id Python.Python.3.12 --exact
winget install --id astral-sh.uv --exact
```

關閉並重新開啟 PowerShell，再安裝 pnpm：

```powershell
npm install --global pnpm@11.19.0
```

確認安裝成功：

```powershell
node --version
pnpm --version
python --version
uv --version
```

### 3. 安裝 Docker Desktop

下載：[Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

也可以直接執行：

```powershell
winget install --id Docker.DockerDesktop --exact
```

安裝完成後開啟 Docker Desktop，等左下角顯示 **Engine running**。

### 4. 第一次啟動

在專案根目錄開啟 PowerShell，依序執行：

```powershell
Copy-Item .env.example .env
pnpm install
docker compose pull db
pnpm db:up
pnpm db:migrate
```

`.env.example` 會提交到 Git，提供變數名稱與本機開發預設值；`.env` 是由它複製出的本機設定，不提交到 Git。範例中的帳號與密碼只適用於本機 Docker，不可用於正式環境。

`docker compose pull db` 會下載 PostGIS image；`pnpm db:up` 會建立並啟動資料庫容器，不需要手動複製 Docker 資料庫。

### 5. 啟動網站

開啟兩個 PowerShell 視窗：

```powershell
# 視窗 1：後端
pnpm dev:backend
```

```powershell
# 視窗 2：前端
pnpm dev:frontend
```

### 5-1. 建立管理員

網站啟動後，第一次進入管理後台前建立管理員，密碼至少 6 個字元：

```powershell
pnpm admin:create --email admin@example.local --password "請替換成至少6字元的密碼"
```

管理員登入網址：<http://localhost:3000/admin/login>

一般使用者首頁：<http://localhost:3000>

公開店家地圖：<http://localhost:3000/map>

一般使用者登入與管理員登入分開；店家新增、編輯、發布及封存等管理功能請從此管理後台進入。

### 查看 PostgreSQL 資料表

資料庫啟動後，在專案根目錄執行以下指令進入 PostgreSQL：

```powershell
docker compose exec db psql -U bitemap -d bitemap
```

進入 PostgreSQL 後，查看所有資料表：

```sql
\dt
```

查看特定資料表結構或資料：

```sql
\d restaurants
SELECT * FROM restaurants;
```

離開 PostgreSQL：

```sql
\q
```

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

| 層級           | 技術                                                         | 用途與選擇理由                                                                                |
| -------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------- |
| Web／PWA       | Next.js App Router、React、TypeScript                        | 建立響應式 Web；後續加入 Manifest、Service Worker、安裝與 Web Push，不需重寫前端              |
| UI             | Tailwind CSS、shadcn/ui                                      | 建立一致的元件與設計 Token，同時保留客製化空間                                                |
| 表單與驗證     | React Hook Form、Zod                                         | 處理登入、留言、約飯與個人資料表單；提供前端即時驗證                                          |
| 伺服器狀態     | TanStack Query                                               | 管理 API 快取、重新驗證、分頁、樂觀更新與錯誤重試                                             |
| 輕量前端狀態   | Zustand                                                      | 管理篩選條件、建立約飯流程及純 UI 狀態；不複製伺服器資料                                      |
| 地圖渲染       | MapLibre GL JS                                               | 負責 2D 地圖畫布、縮放、拖曳、圖釘與互動事件；Stage 1 管理地圖與 Stage 2 公開地圖共用渲染核心 |
| 地圖底圖       | OpenFreeMap                                                  | 提供道路、區域與地名底圖；目前使用 Positron 2D style，不放入 3D 建築圖層                      |
| 地圖資料格式   | GeoJSON                                                      | 將後端回傳的資料庫店家轉成地圖來源，支援群聚與單店圖層                                        |
| 店家群聚       | MapLibre GeoJSON source clustering                           | 公開地圖依縮放層級將資料庫店家合併成群聚圓圈並顯示店家數量                                    |
| 料理分類標記   | MapLibre circle／symbol layer + cuisine color                | 單店放大後使用資料庫料理分類色票顯示標記，並以圖例、文字或圖示輔助辨識                        |
| 地圖搜尋       | FastAPI map search + Geocoding Provider                      | 搜尋列分離處理地區／地址與 BiteMap 已發布店家，最多回傳 5 筆候選                              |
| 地圖篩選       | PostGIS bounds + city／district／cuisine／price query        | 篩選先暫存，按「套用篩選」後再按「搜尋此區域」查詢，避免每次點擊都發送請求                    |
| 地址搜尋定位   | FastAPI Geocoding Provider（Stage 1 使用 Nominatim adapter） | 將地址轉成座標；結果只用於定位，不會把外部店家寫入或混入 BiteMap 店家資料                     |
| 點圖反向定位   | FastAPI reverse geocoding endpoint                           | 管理員在地圖點擊或拖曳後，將座標轉回地址並同步到新增／編輯店家表單                            |
| API            | Python、FastAPI、Pydantic                                    | 實作 REST API、權限與商業規則；亦方便後續加入評論分析與 AI 摘要                               |
| ORM／Migration | SQLAlchemy 2、Alembic                                        | 明確管理資料存取、交易與資料庫版本變更                                                        |
| API 合約       | OpenAPI + 產生式 TypeScript Client                           | 由 FastAPI 規格產生前端型別與 Client，避免前後端欄位不一致                                    |
| 主資料庫       | PostgreSQL                                                   | 儲存使用者、餐廳、留言、再訪、約飯、投票、訊息與社交關係等交易資料                            |
| 空間資料       | PostGIS                                                      | 儲存餐廳座標、距離篩選、範圍查詢與地圖資料                                                    |
| 快取／即時協調 | Redis                                                        | 快取熱門查詢、限流、WebSocket Pub/Sub、背景工作 Broker；不作永久資料來源                      |
| 背景工作       | Celery                                                       | 執行通知、AI 摘要、評論可信度分析、圖片處理及未來區域資料蒐集等非同步工作                     |
| 即時通訊       | FastAPI WebSocket + Redis Pub/Sub                            | 支援私訊、好友聊天及約飯聊天室；所有訊息仍寫入 PostgreSQL                                     |
| 檔案儲存       | S3 相容 Object Storage                                       | 儲存頭像、留言照片、餐點照片與菜單素材；資料庫只保存中繼資料與物件鍵值                        |
| 測試           | Pytest、Vitest、React Testing Library、Playwright            | 分別覆蓋後端、前端元件與跨模組核心流程                                                        |
| 開發環境       | Docker Compose、pnpm、uv                                     | 讓 Web、API、Worker、PostgreSQL 與 Redis 可重現地在本機啟動                                   |
| CI/CD          | GitHub Actions、Docker                                       | 執行格式檢查、型別檢查、測試、Migration 檢查與映像建置                                        |
| 可觀測性       | OpenTelemetry、Sentry、結構化 JSON Log                       | 追蹤 API、背景工作與前端錯誤，並保留跨服務 Trace ID                                           |

### 前端策略

- 採 Mobile First 響應式設計；桌面 Web 與手機版共用同一套頁面及元件。
- Footer 固定為五個主入口：`探索｜地圖｜約飯｜聊天室｜個人頁面`。
- 先完成一般 Web 能力，再加入 PWA Manifest、Service Worker、安裝提示與 Web Push。
- 餐廳公開資訊可使用 Server Components／SSR；需要登入的聊天、投票及個人操作以 Client Components 與 API 查詢為主。
- 定位功能只在使用者明確同意後啟用；拒絕定位時依序使用上次瀏覽位置與系統預設城市。
- MVP 不將離線編輯與離線訊息列為必要能力；Service Worker 先快取 App Shell 與安全的靜態資源。

### 地圖架構

地圖採「後端可視範圍查詢＋前端渲染」；Stage 2 先顯示單店，Stage 3 加入搜尋、篩選與前端群聚：

```text
取得目前位置 / 上次位置 / 預設城市
                  ↓
顯示地圖與已載入結果。前端使用 MapLibre GL JS 渲染，Stage 1 先使用不需 API Key 的 OpenFreeMap；後續可替換圖磚供應商。
                  ↓
搜尋列：地區／地址或已發布店家名稱
                  ↓
篩選面板：縣市／行政區、價格、料理分類
                  ↓
使用者拖曳或縮放地圖
                  ↓
顯示「搜尋此區域」按鈕
                  ↓
GET /api/v1/map/restaurants
  bounds + city + district + cuisine + price
                  ↓
PostGIS 查詢範圍內 published 店家
                  ↓
Stage 2：MapLibre DOM Marker 顯示單店
Stage 3：GeoJSON source 依縮放層級群聚
                  ↓
群聚標記 ──點擊──> 自動放大並拆群
單店標記 ──點擊──> 底部預覽卡 ──> 餐廳詳細頁
```

- 地圖 API 接收目前可視範圍 `west/south/east/north`、縮放層級、料理分類及價格條件。
- 只有 `published` 店家可以由公開地圖 API 回傳；管理狀態不得依賴前端過濾。
- 餐廳位置使用 PostGIS `geography(Point, 4326)`，並建立 GiST 空間索引。
- Stage 2 由 API 回傳範圍內的店家點位，瀏覽器以 MapLibre DOM Marker 顯示單店；Stage 3 加入地區／地址與店家名稱搜尋、篩選面板，再改用 GeoJSON source clustering 計算畫面群聚。
- 地圖搜尋 API 將 Geocoding Provider 的地區結果與 BiteMap `published` 店家結果分組回傳；外部地理編碼不會直接寫入店家資料。
- 篩選面板預設收起，套用後顯示條件標籤；只有點擊「搜尋此區域」才依最新 bounds 與條件查詢。
- 群聚數量在 100 家以下顯示精確值，超過 100 家只改變顯示文字為 `100+`，不可修改實際群聚數量。
- Stage 3 點擊群聚時使用群聚邊界自動放大；放大至單店後，使用 MapLibre 自訂 DOM Marker 顯示店家。
- 單店標記顏色由管理員設定的主要料理分類決定。料理分類需有固定色票，並搭配圖例、圖示或文字，符合無障礙辨識需求。
- 點擊單店標記只開啟底部預覽卡，不立即導頁。預覽卡再連至既有餐廳詳細頁。
- 地圖移動後只標示查詢範圍已改變；直到使用者點擊「搜尋此區域」才送出新請求，避免拖曳時頻繁查詢。
- 查詢期間保留舊結果並顯示載入狀態；請求失敗時保留舊結果、顯示重試操作，不清空整張地圖。
- 若結果超過前端安全上限，API 回傳「請放大地圖」狀態；未來資料量達到監控門檻後，再將群聚計算移至 PostGIS，而不改變使用者操作。

### 店家管理與未來資料蒐集

MVP 由管理員維護正式店家：

- 管理員可輸入地址，透過 Geocoding Provider 取得候選位置。
- 台灣地址會先移除前置郵遞區號，並將「縣市／區／里／道路／門牌」轉成 Provider 較容易比對的「門牌／道路／行政區」查詢格式。
- 管理員也可直接點擊地圖建立位置；點擊或拖曳完成後會呼叫反向定位，將可取得的地址自動同步回表單。
- 地址定位服務只負責地址與座標轉換，不負責提供店家清單；公開地圖的店家永遠來自 BiteMap `published` 資料。
- 儲存時必須包含標準化地址、座標、主要料理分類、價格區間及發布狀態；目前可選填一個 `menu_url` 菜單網址。
- 管理後台可查看與開啟菜單網址；目前先不處理菜單圖片、PDF 上傳及菜單品項，後續可再調整資料模型。
- 店家管理提供地區／地址關鍵字、料理分類與狀態篩選；目前在前端即時篩選，資料量增大後再改為後端查詢。
- 一般使用者沒有新增或發布店家的權限。

管理後台目前包含：管理員登入、料理分類 CRUD、固定／自訂料理色票、料理圖示預覽、店家新增與編輯、地圖點選及拖曳座標、菜單網址、發布／封存／解封、店家刪除，以及店家篩選。料理分類可停用／啟用，未被店家使用時可刪除；分類與店家清單每頁最多顯示 8 筆，超過時使用分頁。料理分類的顯示名稱給人閱讀，識別名稱（slug）給 API 與資料庫使用；slug 會由顯示名稱自動產生，也可在進階設定手動調整。

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
- 關聯式 schema 維持第三正規化（3NF）；可獨立查詢的業務事實拆成關聯表，避免以 JSON 或重複欄位取代正式關聯。
- 身分模型預留 `user`、`admin`、`merchant` 三種角色；一般登入與管理員登入分開，商家編輯權限不會由一般使用者登入取得。
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
│   ├── frontend/            # Next.js Web / PWA
│   ├── backend/             # FastAPI modular monolith
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
