# Stage 7 約飯與投票設計

## 範圍與決定

Stage 7 完成 BiteMap 的約飯與多人選店閉環，聊天室仍留在 Stage 8。介面沿用既有 BiteMap 的暖白底、珊瑚色操作按鈕與細框卡片，參考確認的版型方向採用膠囊式「公開約飯／我的約飯」切換、狀態 chip、投票進度與成員頭像堆疊。

- 公開約飯：建立、直接加入、退出、發起人移除、候選餐廳、投票與結算。
- 私人約飯：建立、申請加入、發起人接受／拒絕、退出與移除。
- 一場約飯最多三家候選餐廳；從餐廳詳情頁發起時，該餐廳自動成為候選 1。
- 正式成員每場只能對一間候選餐廳投一票；重新投票會取代舊票。
- 平票時只從平手候選餐廳中隨機選出結果，結果一經產生即固定保存。
- 公開約飯額滿、截止時間到達或發起人手動開始後進入投票。

以下內容維持未實作，因為需求尚未決定：私人約飯的條件設定、私人約飯是否進入候選餐廳投票、私人約飯的截止與開始投票規則、候補名單與聊天室。

## 資料模型

### `meal_events`

一列代表一場約飯。包含發起人、可見性 `public|private`、主旨、用餐時間、人數上限、加入截止時間、目前狀態與投票結果餐廳。公開約飯狀態為 `open|voting|decided|cancelled|completed`；私人約飯僅使用 `open|cancelled|completed`，不會自行進入投票。

### `meal_memberships`

一列代表使用者與約飯的關係，使用 `(meal_event_id, user_id)` 唯一限制。狀態為 `host|member|pending|rejected|left|removed`；只有 `host` 與 `member` 是正式成員，能讀取成員資訊，且只有公開約飯正式成員能投票。

### `meal_candidates`

一列代表約飯候選餐廳，連到既有 `restaurants`。以 `position` 保存候選順序並限制每場最多三筆；餐廳必須是已發布狀態。公開約飯建立時可先不放候選，代表先揪人後選店。

### `meal_votes`

一列代表正式成員在一場公開投票中的目前選擇，`(meal_event_id, voter_id)` 唯一。候選餐廳必須屬於同一場約飯，成員被移除、退出或失去資格時，該票會在結算查詢中排除。

## 權限與狀態規則

- 所有修改端點都使用既有一般使用者 Session，並在後端確認關係與狀態。
- 只有發起人能修改候選餐廳、開始投票、審核私人申請與移除成員。
- 公開約飯在 `open` 且未額滿／未截止時可直接加入；私人約飯在 `open` 時只能建立或重新建立 pending 申請。
- 參與者可在 `open` 或 `voting` 退出；發起人不可在尚有成員時退出，應使用取消或移除流程。
- 公開約飯進入 `voting` 後停止加入與候選餐廳異動；至少一個候選餐廳才能開始投票。
- 結算時在交易內讀取有效正式成員的票數，最高票餐廳勝出；平票以安全隨機選擇一筆並寫入 `decided_restaurant_id`，避免之後讀取結果改變。

## API

- `GET /api/v1/meals?scope=public|mine`：公開可加入飯局或目前使用者相關飯局。
- `POST /api/v1/meals`：建立公開或私人約飯；可選第一家候選餐廳。
- `GET /api/v1/meals/{meal_id}`：讀取可見約飯詳情、候選餐廳、成員摘要與投票結果。
- `POST /api/v1/meals/{meal_id}/join`：公開直接加入，私人建立申請。
- `POST /api/v1/meals/{meal_id}/leave`：正式成員退出。
- `POST /api/v1/meals/{meal_id}/members/{user_id}/approve|reject|remove`：發起人管理私人申請與正式成員。
- `POST /api/v1/meals/{meal_id}/candidates`、`DELETE /api/v1/meals/{meal_id}/candidates/{candidate_id}`：發起人管理公開約飯候選。
- `POST /api/v1/meals/{meal_id}/start-voting`、`POST /api/v1/meals/{meal_id}/votes`、`POST /api/v1/meals/{meal_id}/finalize-vote`：公開飯局的投票狀態轉換與投票。

所有回應都只回傳必要公開個人資料；未登入為 401、無權限為 403、不存在或不可見資源為 404、不合法狀態轉換或欄位為 422。

## 前端流程

`/meals` 取代目前的準備中頁面：

1. 上方提供「公開約飯／我的約飯」分頁與建立按鈕。
2. 公開卡片顯示發起人、時間、簡介、目前人數、狀態、候選餐廳或已選餐廳、成員頭像與加入行動。
3. 投票中的卡片顯示候選餐廳、票數與比例；符合資格的目前使用者可選擇或更換一票。
4. 建立流程使用手機友善 bottom sheet，填寫主旨、用餐時間、人數上限、加入截止、公開／私人與餐廳決定方式；私人模式明確提示「餐廳流程待確認」。
5. 餐廳詳情頁的「發起約飯」啟用，前往建立頁並帶入該餐廳作為候選 1。
6. 頁面包含 loading、empty、error、retry、disabled、success feedback 與 reduced-motion 支援；不使用假頭像、假照片或假飯局。

## 測試與驗收

- migration upgrade／downgrade 可逆，唯一限制與最多三候選規則有效。
- 公開直接加入、額滿拒絕、私人申請與審核、退出與移除權限都有 API 測試。
- 非正式成員、被移除者與非發起人無法投票或管理候選；重複投票只保留一票。
- 平票結算只會從平手候選選出，結算後結果不會改變。
- 前端涵蓋公開／我的切換、建立 sheet、加入、投票、空白與錯誤狀態；手機與桌面 footer 不遮擋內容。
- OpenAPI 型別、formatter、lint、typecheck、backend／frontend 測試與 production build 必須通過。
