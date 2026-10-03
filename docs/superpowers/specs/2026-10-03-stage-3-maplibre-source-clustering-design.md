# Stage 3 MapLibre GeoJSON Source Clustering 設計

日期：2026-10-03  
狀態：使用者已確認，進入實作

## 範圍

本次先完成 Stage 3 的前端 MapLibre 原生 clustering。保留現有公開地圖 viewport API、篩選、搜尋、預覽卡與群聚展示資料；本次不新增 vector tiles、後端 clustering 或 Redis 快取。

## 設計

- 將目前地圖店家轉成 GeoJSON `FeatureCollection`。
- 使用 MapLibre `geojson` source 的 `cluster: true`、`clusterMaxZoom` 與 `clusterRadius`。
- 以 cluster circle／symbol layer 顯示群聚數量。
- 以 unclustered point layer 顯示主要料理顏色與料理圖示首字。
- 點擊群聚時呼叫 `getClusterExpansionZoom`，再以 `easeTo` 放大到 MapLibre 計算的拆群層級。
- 點擊未群聚店家時，以 feature properties 的店家 ID 找回目前 state 中的店家，沿用現有 `RestaurantPreviewCard`。
- 群聚展示模式與正式店家共用同一個 source 與 layer pipeline，不再使用自訂畫面座標半徑演算法。
- 篩選與 viewport API 仍由現有 `searchMap` 負責；新資料以 `setData` 更新 source，不重建 MapLibre instance。

## 互動與 fallback

- API 請求失敗時保留現有 source data 與目前地圖畫面。
- 沒有店家時移除 source data，顯示既有空結果訊息。
- MapLibre source 尚未建立前，資料先保留在 React state，待 map load 後同步。
- 預覽卡關閉、地圖點擊與搜尋選店行為維持原本規則。

## 驗收與測試

- source 使用 clustering 且正式資料與展示資料都能載入。
- 群聚數量與點位數量正確，點擊群聚會使用 MapLibre expansion zoom。
- 點擊點位仍能開啟正確預覽卡。
- 地圖移動、篩選、搜尋、重試與卸載不殘留 source、layer、listener 或 abort request。
- 通過前端 typecheck、lint 與既有測試。
