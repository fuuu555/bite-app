# BiteMap Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

BiteMap 的主要使用者是在台灣尋找附近餐廳的人。使用者可能允許瀏覽器定位，也可能拒絕定位；兩種情況都必須能繼續使用公開地圖。

管理員是獨立角色，負責建立、定位、分類、發布與封存正式店家。一般使用者不能編輯店家資料。`merchant` 角色目前僅預留，尚未開放店家編輯流程。

## Product Purpose

BiteMap 讓使用者從地圖與探索流程尋找餐廳，查看平台整理的店家資訊，並在後續階段延伸到評價、再訪、收藏、約飯、聊天與個人美食紀錄。

目前 Stage 2 的成功標準是：使用者能在手機與桌面瀏覽器開啟公開地圖、取得或略過定位、搜尋目前可視區域，並查看資料庫中已發布的店家。

## Positioning

公開地圖只呈現 BiteMap 資料庫中經管理流程發布的店家。外部地址服務只協助地址與座標轉換，不會把未審核的外部店家直接混入正式結果。

## Operating Context

- 使用者端主要入口為 `/`，地圖功能位於 `/map`。
- 主導覽固定為五個入口：探索、地圖、約飯、聊天室、個人。
- Stage 2 尚未完成的約飯、聊天室與個人功能會導向清楚的「功能準備中」頁面。
- 第一次進入地圖時依序使用目前位置、上次位置與預設位置；已確認預設位置為桃園中壢。
- 地圖移動後不立即查詢；使用者點擊「搜尋此區域」後才查詢最新可視範圍。

## Capabilities and Constraints

- 前端使用 Next.js、React、TypeScript、Tailwind CSS 與分離的 Web／Mobile CSS。
- 地圖使用 MapLibre GL JS 與 OpenFreeMap 2D 底圖。
- 後端使用 FastAPI、SQLAlchemy、PostgreSQL 與 PostGIS。
- 公開地圖 API 必須使用可視範圍查詢，且只回傳 `published` 店家。
- 查詢期間保留舊結果；定位、底圖或 API 失敗時提供可理解的降級與重試操作。
- Stage 2 顯示單店標記與底部預覽卡；完整群聚、料理篩選與更完整互動留在 Stage 3。
- 一般使用者登入仍依既定計畫留在 Stage 5，不提前加入 Stage 2。
- 首頁 `/` 的正式探索內容仍是產品 TBD，本階段不得自行定義完整首頁功能。

## Brand Commitments

- 產品名稱為 BiteMap。
- 介面以繁體中文為主，程式碼與必要技術註解使用中英文。
- 現有品牌基礎包含珊瑚橘行動色、深青墨色、暖白背景與料理分類色票；新增使用者介面需與既有管理端保持同一產品識別。

## Evidence on Hand

- `FUNCTIONAL_REQUIREMENTS.md`：完整產品需求與尚未決定項目。
- `DEVELOPMENT_PLAN.md`：分階段開發內容與 Stage 2 驗收條件。
- `README.MD`：技術架構、地圖策略與本機開發方式。
- `apps/frontend/src/styles/tokens.css`：目前共用色彩、圓角、陰影與動效 Token。
- 目前沒有可供公開地圖使用的正式品牌攝影或店家照片，不得虛構店家圖片。

## Product Principles

1. 正式店家資料以 PostgreSQL 為唯一真實來源。
2. 沒有定位權限仍可正常使用產品。
3. 地圖查詢由使用者明確觸發，避免拖曳時頻繁更新與畫面跳動。
4. 顏色不是唯一資訊來源，料理分類需搭配文字或圖示辨識。
5. 未完成與未決定的功能清楚標示，不以假資料或假流程冒充完成。

## Accessibility & Inclusion

- 核心操作需支援鍵盤與清楚的焦點狀態。
- 互動控制需維持足夠的點擊範圍與文字對比。
- 地圖以外需提供可理解的載入、空資料、定位拒絕與錯誤訊息。
- 料理分類不可只依靠顏色傳達資訊。
