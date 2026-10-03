# Explore 推薦排序與地址搜尋設計

日期：2026-10-03  
狀態：使用者已確認，進入實作

## 背景

Explore 目前使用可重現的店名排序，`推薦排序` 尚未代表真正的推薦。搜尋也只支援店名包含比對，尚未支援地址關鍵字。料理分類已有獨立 filter，因此不新增料理關鍵字全文搜尋。

## 目標

- 建立可解釋、可測試的推薦排序。
- 讓使用者能以店名或地址搜尋已發布店家。
- 讓推薦排序與 Top 3、完整列表共用同一個排序來源。
- 在外部 Google 資料或 App 資料缺少時仍能正常排序。

## 非目標

- 不顯示一個讓使用者誤以為是客觀評價的綜合分數。
- 不在本階段建立正式評論防作弊或可信度演算法。
- 不搜尋 Google 店家資料、外部 Geocoding 結果或外部菜單內容。
- 不新增料理關鍵字搜尋；料理分類維持獨立 filter。

## 推薦排序

### 分數公式

```text
recommendation_score =
  sum(valid_signal_score * signal_weight) /
  sum(valid_signal_weight)
```

每個店家只使用目前有資料的 signal。缺少的 signal 不補 0 分，也不讓店家直接淘汰；該 signal 的權重從分母移除後，剩餘權重重新正規化。

### Signal 與權重

| Signal | 權重 | v1 計算 |
| --- | ---: | --- |
| 距離 | 25% | 0 公尺為 100 分、10 公里為 0 分，線性換算並限制在 0–100。沒有定位或距離時略過。 |
| App 再訪率 | 30% | 使用有效 App 評價中的 `will_return` 比例，直接作為 0–100 分。 |
| Google 評分 | 15% | `rating / 5 * 100`。沒有 Google 評分時略過。 |
| 評論可信度 | 15% | 暫以 App 有效評價人數作 v1 proxy：1–2 人為 25、3–9 人為 60、10 人以上為 100。沒有有效評價時略過。 |
| 價格 | 15% | 只有使用者選擇價格 filter 時啟用；符合 filter 的結果為 100 分。沒有選價格 filter 時略過。 |

評論可信度 v1 只代表資料量 proxy，不宣稱評論真實或沒有灌票；Stage 6 正式可信度演算法完成後，替換此 signal 的計算方式，不改變排序介面。

### 排序模式

API 的 `sort` 支援：

- `recommended`：依上述推薦分數由高到低。
- `distance`：距離由近到遠，缺少距離排後。
- `price`：價格區間由低到高。
- `revisit_rate`：App 再訪率由高到低，缺少資料排後。
- `google_rating`：Google 評分由高到低，缺少資料排後。
- `trust`：可信度 proxy 由高到低，缺少資料排後。

推薦排序同分時依序使用 App 再訪率、Google 評分、距離、店名與 ID 作為穩定 tie-breaker。Top 3 與完整列表從同一個已排序陣列取值；推薦分數不加入 API response，也不顯示在前端。

## 地址關鍵字搜尋

### 查詢範圍

Explore 的 `q` 同時搜尋已發布店家的名稱與地址。查詢結果不得包含草稿、封存或未完成公開必要欄位的店家。地圖搜尋維持現有店名搜尋與地區／料理／價格 filter，不在本設計擴張地圖搜尋行為。

### PostgreSQL 實作

採混合搜尋以兼顧 PostgreSQL Full Text Search 與中文地址：

1. Full Text Search：以店名與地址建立 `tsvector`，使用 PostgreSQL `simple` configuration 與 `websearch_to_tsquery`。
2. `pg_trgm` fallback：對正規化後的店名與地址做 trigram 比對，補足中文連續文字不一定能被 `simple` tokenizer 拆分的情況。
3. 地址正規化：查詢與資料同步處理台／臺、空白、標點等已定義的台灣地址變體。
4. 建立對應 GIN index；migration 必須包含既有資料回填與新資料的同步更新方式。

Full Text Search 或 trigram 任一方式命中即可回傳，仍由既有穩定排序或使用者選擇的排序模式決定順序。不使用外部 Geocoding，也不把 Google API 結果寫入搜尋索引。

## UI 與 API

- Explore 搜尋提示改為「搜尋店家名稱或地址」。
- 排序下拉啟用推薦、距離、價格、App 再訪率、Google 評分與評論可信度。
- 查詢參數保留在 Explore URL，重新整理與上一頁／下一頁可恢復 `q`、filter 與 `sort`。
- Google API 暫時失敗時，Google signal 略過，其他有效 signal 仍可完成推薦排序。

## 測試

- ranking unit tests：完整資料、缺 Google、缺 App 評價、缺定位、缺價格 filter、全部 signal 缺少，以及 tie-breaker。
- API tests：每種 `sort`、Top 3 與完整列表順序一致、地址中文關鍵字、店名或地址 OR 查詢、僅回傳 published 店家。
- migration／database tests：搜尋索引可建立，既有店家可被搜尋。
- frontend tests：排序參數序列化、排序選項、搜尋提示與 URL 恢復。

## 實作順序

1. 先建立 ranking signal／score service 與後端測試。
2. 更新 Explore API 的排序參數與資料載入順序，確保 Google／App signal 在排序前完成。
3. 建立地址搜尋 migration、索引與查詢測試。
4. 啟用前端排序 UI、搜尋提示與 URL 同步。
5. 執行 backend、frontend、typecheck 與 lint 驗證。
