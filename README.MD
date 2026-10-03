# BiteMap

## 快速啟動（Windows 11）

### 1. 安裝工具

`winget` 是 Windows 用來安裝軟體的指令工具。用 PowerShell 安裝 Node.js、Python 和 `uv`：

```powershell
winget install --id OpenJS.NodeJS.LTS --exact
winget install --id Python.Python.3.12 --exact
winget install --id astral-sh.uv --exact
```

安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，開啟後等到顯示 **Engine running**。關閉並重新開啟 PowerShell，再安裝 pnpm：

```powershell
npm install --global pnpm@11.19.0
```

### 2. 下載專案並準備資料庫

```powershell
git clone https://github.com/fuuu555/bite-app.git
cd bite-app
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
pnpm install
pnpm db:up
pnpm db:migrate
```

### 3. 啟動網站

開兩個 PowerShell 視窗，都在 `bite-app` 專案資料夾內執行。

視窗一（後端）：

```powershell
pnpm dev:backend
```

視窗二（前端）：

```powershell
pnpm build:frontend
pnpm --dir apps/frontend start
```

開啟 <http://localhost:3000>。前端程式更新後，按 `Ctrl+C` 停止前端，再重新執行上面兩個前端指令。

### 4. 登入管理員並新增店家

先在第三個 PowerShell 視窗建立管理員帳號。把信箱 `"admin@example.local"` 和密碼換成自己的；密碼至少 6 個字元：

```powershell
pnpm admin:create --email "admin@example.local" --password "請換成自己的密碼"
```

前往 <http://localhost:3000/admin/login> 登入，接著：

1. 開啟「店家管理」，按「新增店家」。
2. 填寫店家資料，選擇料理分類與對應的圖示。
3. 如果需要新增或調整圖示分類，開啟「圖示分類」管理。

店家儲存後即可在 BiteMap 查看。只測試管理員平台不需要設定 Google 登入。

## 觀光署資料整合

資料庫啟動並完成 migration 後，可選擇以下任一方式匯入最新資料：

- **管理員平台：**登入後開啟「觀光署資料店家」，按「一鍵匯入最新資料」。
- **PowerShell 指令：**在專案根目錄執行以下命令，匯入全部觀光署資料：

```powershell
uv run --project apps/backend python apps/backend/scripts/import_tourism_data.py
```




## 核心技術選型

| **層級** | **技術** | **用途與選擇理由** | **實作狀態** |
| --- | --- | --- | --- |
| Web／PWA | Next.js App Router、React、TypeScript | 建立響應式 Web；PWA Manifest、Service Worker、安裝與 Web Push 可在同一前端逐步加入 | **部分實作**：Web 已使用；PWA 安裝、Service Worker、Push 尚未實作 |
| UI | Tailwind CSS、專案自訂 CSS／元件 | 建立一致的樣式與可重用介面，同時保留客製化空間 | **已實作** |
| 輕量前端狀態 | React external store + sessionStorage | 管理目前分頁的約飯草稿與純 UI 狀態；不複製伺服器資料 | **已實作**：約飯草稿使用 React 外部 store 與 sessionStorage |
| 地圖渲染 | MapLibre GL JS | 負責 2D 地圖畫布、縮放、拖曳、圖釘與互動事件；管理地圖與公開地圖共用渲染核心 | **已實作** |
| 地圖底圖 | OpenFreeMap | 提供道路、區域與地名底圖；目前使用 Positron 2D style，不放入 3D 建築圖層 | **已實作** |
| 地圖資料格式 | GeoJSON | 將後端回傳的資料庫店家轉成地圖來源，支援群聚與單店圖層 | **已實作** |
| 店家群聚 | MapLibre GeoJSON source clustering | 依縮放層級將地圖店家合併成群聚圓圈並顯示店家數量 | **已實作** |
| 料理分類標記 | MapLibre circle／symbol layer + cuisine color | 使用分類色彩及圖示呈現單店標記，輔助辨識店家分類 | **已實作** |
| 地圖搜尋 | FastAPI map search + Geocoding Provider | 分開處理地區／地址與 BiteMap 已發布店家，最多回傳 5 筆候選 | **已實作** |
| 地圖篩選 | PostGIS bounds + city／district／cuisine／price query | 依地圖範圍、縣市、行政區、料理分類與價格查詢 | **已實作** |
| 地址搜尋定位 | FastAPI Geocoding Provider（目前使用 Nominatim adapter） | 將地址轉成座標；結果只用於定位，不會把外部店家寫入或混入 BiteMap 店家資料 | **已實作** |
| 點圖反向定位 | FastAPI reverse geocoding endpoint | 管理員在地圖點擊或拖曳後，將座標轉回地址並同步到新增／編輯店家表單 | **已實作** |
| 外部店家資料 | Google Places API (New) | 管理員可切換自動查詢；啟用時綁定 `google_place_id`，探索與詳情只讀取 rating／userRatingCount，不抓取評論內容 | **已實作** |
| API | Python、FastAPI、Pydantic | 實作 REST API、權限與商業規則；亦可供未來評論分析與 AI 摘要功能使用 | **部分實作**：API、權限與主要產品規則已實作；評論分析與 AI 摘要未實作 |
| ORM／Migration | SQLAlchemy 2、Alembic | 管理資料存取、交易與資料庫版本變更 | **已實作** |
| API 合約 | OpenAPI + 產生式 TypeScript Client | 由 FastAPI 規格產生前端型別與 Client，避免前後端欄位不一致 | **已實作**：專案含 OpenAPI TypeScript 產生流程 |
| 主資料庫 | PostgreSQL | 儲存使用者、店家、留言、再訪、約飯、投票、訊息與社交關係等交易資料 | **已實作** |
| 空間資料 | PostGIS | 儲存店家座標、距離篩選、範圍查詢與地圖資料 | **已實作** |
| 快取／即時協調 | Redis | 用於 WebSocket Pub/Sub 與多執行個體協調；不作永久資料來源 | **部分實作**：WebSocket Pub/Sub 已使用；地圖目前是 process-local TTL 快取，跨執行個體共享快取、限流與背景工作 Broker 尚未導入 |
| 背景工作 | Celery | 執行通知、AI 摘要、評論可信度分析、圖片處理及未來區域資料蒐集等非同步工作 | **尚未實作** |
| 即時通訊 | FastAPI WebSocket + Redis Pub/Sub | 支援私訊、好友聊天及約飯聊天室；所有訊息仍寫入 PostgreSQL | **已實作** |
| 檔案儲存 | S3 相容 Object Storage | 儲存頭像、留言照片、餐點照片與菜單素材；資料庫只保存中繼資料與物件鍵值 | **尚未實作**：目前未使用 S3 相容服務 |
| 測試 | Pytest、Vitest、Playwright | 覆蓋後端、前端邏輯與跨模組核心流程 | **已實作** |
| 開發環境 | Docker Compose、pnpm、uv | 讓 Web、API、PostgreSQL 與 Redis 可重現地在本機啟動 | **已實作** |
| CI/CD | GitHub Actions、Docker | 執行格式檢查、型別檢查、測試、Migration 檢查與映像建置 | **部分實作**：GitHub Actions CI 已有；Docker 映像建置／部署流程尚未完成 |
| 可觀測性 | OpenTelemetry、Sentry、結構化 JSON Log | 追蹤 API、背景工作與前端錯誤，並保留跨服務 Trace ID | **部分實作**：已有地圖查詢監控資訊；OpenTelemetry 與 Sentry 尚未導入 |

## 專案結構

```text
bite-app/
├── apps/
│   ├── frontend/                 # Next.js 網頁與管理員平台
│   │   └── src/
│   │       ├── app/              # 網頁路由與管理後台入口
│   │       ├── features/         # home、map、meals、chat、profile、restaurants、admin
│   │       ├── shared/           # auth、realtime、ui 等共用功能
│   │       └── styles/           # 全域樣式
│   └── backend/                  # FastAPI 後端
│       ├── migrations/           # Alembic 資料庫版本
│       ├── scripts/               # 維運指令，例如觀光署資料匯入
│       ├── src/api/
│       │   ├── core/             # 設定、資料庫與安全性
│       │   ├── domain/           # 資料模型與 API schemas
│       │   ├── integrations/     # Google、地理編碼等外部服務
│       │   ├── routers/          # API 路由，含觀光資料管理
│       │   ├── services/         # 店家、地圖、聊天、觀光資料等功能邏輯
│       │   └── realtime.py       # WebSocket 即時通訊入口
│       └── tests/                # 後端測試
├── packages/
│   └── api-client/               # 前後端共用的 API client
├── tests/
│   └── e2e/                      # Playwright 網站流程測試
├── docs/superpowers/
│   ├── specs/                    # 功能設計文件
│   └── plans/                    # 實作計畫
├── .github/workflows/            # GitHub Actions CI
├── docker-compose.yml            # 本機 PostgreSQL／PostGIS 與 Redis
├── package.json                  # 專案常用指令
├── pnpm-workspace.yaml           # pnpm workspace 設定
├── .env.example                  # 本機環境設定範例
├── README.MD                     # 快速啟動與專案簡介
├── RULE.md                       # 開發規則
├── FUNCTIONAL_REQUIREMENTS.md    # 功能需求
└── DEVELOPMENT_PLAN.md           # 開發階段規劃
```
