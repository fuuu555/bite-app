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
docker compose pull db redis
pnpm db:up
pnpm db:migrate
```

`.env.example` 會提交到 Git，提供變數名稱與本機開發預設值；`.env` 是由它複製出的本機設定，不提交到 Git。範例中的帳號與密碼只適用於本機 Docker，不可用於正式環境。

`docker compose pull db redis` 會下載 PostGIS 與 Redis image；`pnpm db:up` 會建立並啟動兩個容器，不需要手動複製 Docker 資料庫。Redis 用於 WebSocket 跨 API instance 的即時事件協調，聊天訊息仍永久寫入 PostgreSQL。

前端預設透過 `NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws` 連接共用 WebSocket。部署到 HTTPS 環境時應改為同站或 API 網域的 `wss://` 位址，並把前端 origin 加入 `API_CORS_ORIGINS`；WebSocket 使用既有 HttpOnly 使用者 session cookie 驗證，不在 URL 帶 Token。

### 5. 啟動網站

預設使用 Next.js production 模式啟動前端，避免開發工具、HMR 與按需編譯影響操作速度。開啟兩個 PowerShell 視窗：

```powershell
# 視窗 1：後端
pnpm dev:backend
```

```powershell
# 視窗 2：先建置前端，再啟動 production server
pnpm build:frontend
pnpm --dir apps/frontend start
```

網站啟動後開啟 <http://localhost:3000>。若前端程式碼有修改，請在前端視窗按 `Ctrl+C` 停止 server，重新執行上述兩行指令；不要同時執行 `pnpm dev:frontend`，否則會因 port 3000 已被占用而啟動失敗或改用其他 port。

需要即時更新畫面進行前端開發時，才改用下列開發模式；Next.js 的開發工具與首次進入頁面的編譯延遲只會出現在此模式：

```powershell
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

一般使用者入口：<http://localhost:3000/login>，登入只使用 Google；未登入時需先登入才能進入 App 頁面。

登入後的個人頁：<http://localhost:3000/profile>；個人資料與裝置 Session 管理：<http://localhost:3000/profile/settings>

一般使用者登入與管理員登入分開；店家新增、編輯、發布及封存等管理功能請從此管理後台進入。管理員目前可在「頭貼資產」上傳本地內建頭貼，使用者可在個人設定選擇；S3 Object Storage、簽名上傳與圖片驗證仍待後續階段提供。

正式環境 Google 登入設定：

- `GOOGLE_OAUTH_CLIENT_ID` 與 `GOOGLE_OAUTH_CLIENT_SECRET` 只設定在正式環境的 Secret 管理工具，不提交到 Git 或記錄到部署日誌。
- Google Cloud OAuth Client 的 Authorized redirect URI 必須設定為正式 API 的 `/api/v1/auth/google/callback`，且必須使用 HTTPS。
- `FRONTEND_URL`、`BACKEND_URL` 與 `API_CORS_ORIGINS` 必須改成正式 HTTPS 網域；Session Cookie 也必須在正式環境使用 Secure 設定。
- Google OAuth consent screen、Publishing status 與測試使用者名單需在 Google Cloud Console 完成設定。

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

外部店家資料流程：管理員儲存店家時，可用開關決定是否以店名與地址呼叫 Google Places Text Search，啟用時保存相符的 `google_place_id`；探索列表與餐廳詳情再以該 ID 呼叫 Place Details，只讀取評分與總評論數。測試資料可關閉此開關，避免任何 Google API 請求；Google 評論內容不抓取、不保存，API 失敗時回傳安全空狀態。

Next.js 只負責 Web／PWA 與必要的前端伺服器渲染，不承擔核心商業規則。FastAPI 是唯一的業務 API，統一處理餐廳、評價、再訪、約飯、投票、聊天、社交關係、封鎖與檢舉規則。留言資料以餐廳／使用者唯一 thread 搭配多筆 entry 保存，確保再訪紀錄掛在原評論底下且統計只取最新有效 entry。

### 核心技術選型

| 層級           | 技術                                                     | 用途與選擇理由                                                                   |
| -------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Web／PWA       | Next.js App Router、React、TypeScript                    | 建立響應式 Web；後續加入 Manifest、Service Worker、安裝與 Web Push，不需重寫前端 |
| UI             | Tailwind CSS、shadcn/ui                                  | 建立一致的元件與設計 Token，同時保留客製化空間                                   |
| 表單與驗證     | React Hook Form、Zod                                     | 處理登入、留言、約飯與個人資料表單；提供前端即時驗證                             |
| 伺服器狀態     | TanStack Query                                           | 管理 API 快取、重新驗證、分頁、樂觀更新與錯誤重試                                |
| 輕量前端狀態   | React external store + sessionStorage                    | 管理目前分頁的約飯草稿與純 UI 狀態；不複製伺服器資料                             |
| 地圖渲染       | MapLibre GL JS                                           | 負責 2D 地圖畫布、縮放、拖曳、圖釘與互動事件；管理地圖與公開地圖共用渲染核心     |
| 地圖底圖       | OpenFreeMap                                              | 提供道路、區域與地名底圖；目前使用 Positron 2D style，不放入 3D 建築圖層         |
| 地圖資料格式   | GeoJSON                                                  | 將後端回傳的資料庫店家轉成地圖來源，支援群聚與單店圖層                           |
| 店家群聚       | MapLibre GeoJSON source clustering                       | 公開地圖依縮放層級將資料庫店家合併成群聚圓圈並顯示店家數量                       |
| 料理分類標記   | MapLibre circle／symbol layer + cuisine color            | 單店放大後使用資料庫料理分類色票顯示標記，並以圖例、文字或圖示輔助辨識           |
| 地圖搜尋       | FastAPI map search + Geocoding Provider                  | 搜尋列分離處理地區／地址與 BiteMap 已發布店家，最多回傳 5 筆候選                 |
| 地圖篩選       | PostGIS bounds + city／district／cuisine／price query    | 篩選先暫存，按「套用篩選」後再按「搜尋此區域」查詢，避免每次點擊都發送請求       |
| 地址搜尋定位   | FastAPI Geocoding Provider（目前使用 Nominatim adapter） | 將地址轉成座標；結果只用於定位，不會把外部店家寫入或混入 BiteMap 店家資料        |
| 點圖反向定位   | FastAPI reverse geocoding endpoint                       | 管理員在地圖點擊或拖曳後，將座標轉回地址並同步到新增／編輯店家表單               |
| 外部店家資料   | Google Places API (New)                                  | 管理員可切換自動查詢；啟用時綁定 `google_place_id`，探索與詳情只讀取 rating／userRatingCount，不抓取評論內容 |
| API            | Python、FastAPI、Pydantic                                | 實作 REST API、權限與商業規則；亦方便後續加入評論分析與 AI 摘要                  |
| ORM／Migration | SQLAlchemy 2、Alembic                                    | 明確管理資料存取、交易與資料庫版本變更                                           |
| API 合約       | OpenAPI + 產生式 TypeScript Client                       | 由 FastAPI 規格產生前端型別與 Client，避免前後端欄位不一致                       |
| 主資料庫       | PostgreSQL                                               | 儲存使用者、餐廳、留言、再訪、約飯、投票、訊息與社交關係等交易資料               |
| 空間資料       | PostGIS                                                  | 儲存餐廳座標、距離篩選、範圍查詢與地圖資料                                       |
| 快取／即時協調 | Redis                                                    | 快取熱門查詢、限流、WebSocket Pub/Sub、背景工作 Broker；不作永久資料來源         |
| 背景工作       | Celery                                                   | 執行通知、AI 摘要、評論可信度分析、圖片處理及未來區域資料蒐集等非同步工作        |
| 即時通訊       | FastAPI WebSocket + Redis Pub/Sub                        | 支援私訊、好友聊天及約飯聊天室；所有訊息仍寫入 PostgreSQL                        |
| 檔案儲存       | S3 相容 Object Storage                                   | 儲存頭像、留言照片、餐點照片與菜單素材；資料庫只保存中繼資料與物件鍵值           |
| 測試           | Pytest、Vitest、React Testing Library、Playwright        | 分別覆蓋後端、前端元件與跨模組核心流程                                           |
| 開發環境       | Docker Compose、pnpm、uv                                 | 讓 Web、API、Worker、PostgreSQL 與 Redis 可重現地在本機啟動                      |
| CI/CD          | GitHub Actions、Docker                                   | 執行格式檢查、型別檢查、測試、Migration 檢查與映像建置                           |
| 可觀測性       | OpenTelemetry、Sentry、結構化 JSON Log                   | 追蹤 API、背景工作與前端錯誤，並保留跨服務 Trace ID                              |

### 專案結構

```text
bite/
├── apps/
│   ├── frontend/            # Next.js Web / PWA
│   │   ├── public/          # MapLibre worker 與靜態資源
│   │   └── src/
│   │       ├── app/         # Next.js 路由；只負責頁面入口與組合
│   │       │   ├── (user)/  # 探索、地圖、約飯、聊天室、個人頁與店家頁
│   │       │   └── admin/   # 管理員登入與管理後台路由
│   │       ├── features/    # 依產品功能分組的 API、元件與工具
│   │       │   ├── home/    # 探索首頁與探索 API
│   │       │   ├── map/     # 公開地圖、搜尋、篩選與店家預覽
│   │       │   ├── meals/   # 約飯列表、建立、詳情、投票與飯局聊天
│   │       │   ├── chat/    # 私聊、好友聊與聊天室訊息互動
│   │       │   ├── profile/ # 個人頁、好友社交中心與公開個人頁
│   │       │   ├── restaurants/ # 店家詳情與留言／再訪
│   │       │   └── admin/   # 管理員 API、店家、料理與頭貼管理
│   │       ├── shared/      # 跨功能共用，不放單一產品功能
│   │       │   ├── auth/   # 使用者 API、登入門禁與登入表單
│   │       │   ├── realtime/ # WebSocket／Redis 即時連線與事件
│   │       │   └── ui/     # AppConfirmDialog、Footer 等共用 UI
│   │       └── styles/      # Design tokens、Web 與 Mobile 樣式
│   └── backend/             # FastAPI modular monolith
│       ├── migrations/      # Alembic migration
│       ├── media/            # 本地開發用頭貼檔案（上傳檔案不提交）
│       ├── src/api/
│       │   ├── core/        # 設定、資料庫與安全性
│       │   ├── domain/      # ORM models 與 API schemas
│       │   ├── integrations/ # Google OAuth、Places 與 Geocoding adapters
│       │   ├── routers/     # Admin、Auth、Explore、Map、Reviews 與 Meals API
│       │   ├── services/    # 店家、探索、地圖、個人資料、留言、約飯、頭貼與排序邏輯
│       │   ├── scripts/     # 維運／初始化腳本
│       │   └── main.py      # FastAPI application entrypoint
│       └── tests/           # 後端測試
├── packages/
│   └── api-client/          # OpenAPI 產生的 TypeScript Client
├── tests/
│   └── e2e/                 # 依功能命名的 Playwright 跨模組測試
├── docs/superpowers/specs/  # 功能設計規格
├── .github/workflows/       # CI workflow
├── docker-compose.yml       # 本機 PostgreSQL／PostGIS 與 Redis
├── FUNCTIONAL_REQUIREMENTS.md
├── DEVELOPMENT_PLAN.md
├── RULE.md
├── package.json
├── pnpm-workspace.yaml
└── README.MD
```

### 前端檔案怎麼找

前端採「路由薄、功能厚、共用獨立」的分層方式：

1. **先找網址對應的 route**：從 `apps/frontend/src/app/` 開始。這裡的 `page.tsx` 應只負責載入與組合功能元件，不放完整商業邏輯。
2. **再找功能元件**：依頁面所屬功能進入 `apps/frontend/src/features/<feature>/components/`，例如聊天室使用 `features/chat`，約飯使用 `features/meals`。
3. **需要呼叫 API 時**：先看同一個 feature 下的 `api/`；OpenAPI 產生的共用型別與 client 在 `packages/api-client/`。
4. **需要跨功能共用時**：放到 `apps/frontend/src/shared/`，目前分為 `auth`、`realtime`、`ui`。只有至少兩個功能共同使用的程式才放這裡。
5. **需要格式化或樣式時**：全域樣式在 `apps/frontend/src/styles/`；單一元件的樣式優先留在元件本身或既有 design token 範圍內。

功能資料夾的常見責任如下：

| 目錄                            | 放什麼                                 | 不放什麼                         |
| ------------------------------- | -------------------------------------- | -------------------------------- |
| `features/<feature>/api`        | 該功能的 API 呼叫、資料轉換與 API 測試 | 跨功能的登入、WebSocket 基礎連線 |
| `features/<feature>/components` | 該功能的頁面元件與區塊元件             | Next.js 路由入口                 |
| `features/<feature>/utils`      | 該功能的純函式、草稿或排序邏輯         | React 元件與伺服器資料快取       |
| `shared/auth`                   | 使用者身分、登入與 App 門禁            | 單一頁面的 profile UI            |
| `shared/realtime`               | WebSocket 連線、訂閱與共用事件         | 聊天訊息呈現 UI                  |
| `shared/ui`                     | 多個功能會使用的共用 UI                | 只服務單一功能的按鈕或表單       |
