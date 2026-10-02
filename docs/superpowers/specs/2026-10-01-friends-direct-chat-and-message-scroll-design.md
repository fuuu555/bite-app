# Stage 8：好友、私訊與聊天室排序設計

日期：2026-10-01  
狀態：已由使用者確認設計，待 implementation plan

## 背景

目前 Stage 8 第一批已完成約飯聊天室、單一 `/api/v1/ws`、Redis Pub/Sub、PostgreSQL 訊息保存與聊天室列表。下一批要修正聊天畫面中新訊息偶爾不在預期位置的問題，並啟用聊天室中的「私訊」與「好友」功能。

本批不加入圖片、已讀狀態、輸入中提示或訊息收回。

## 已確認的產品規則

### 聊天排序

- 訊息由舊到新排列，新訊息固定出現在底部。
- 初次載入歷史訊息後，畫面定位在最底部。
- 使用者接近底部時收到新訊息，畫面自動捲到底部。
- 使用者正在往上閱讀歷史時，不強制跳動，顯示「N 則新訊息」提示。
- 點擊提示後回到底部並清除提示。
- 載入較早訊息時保留目前畫面 anchor，避免內容插入後跳動。
- 訊息排序使用伺服器 `created_at` 加穩定 message id 做 deterministic tie-breaker，不能依賴 WebSocket 抵達順序。

### 好友

- 好友是雙向關係，需要對方接受。
- 支援送出、接受、拒絕、取消好友邀請與解除好友。
- 成為好友後沿用原本私訊 conversation，不建立新的聊天室，也不搬移訊息。
- 原私訊會從「私訊」分類轉入「好友」分類。
- 解除好友後，原 conversation 保留並回到「私訊」分類。
- 可以從其他使用者的個人頁加好友或發私訊。

### 私訊

- 陌生人可以發第一則私訊。
- 收件者尚未回覆前，原發送者不能連續大量傳訊；第一批採一則待回覆限制。
- 收件者回覆後解除該限制，但仍受一般訊息頻率限制。
- 使用者可以設定是否接受陌生人私訊。
- 好友之間不受陌生人私訊限制。

### 封鎖

- 支援封鎖與解除封鎖。
- 封鎖後立即移除雙方好友關係與未完成的好友邀請。
- 被封鎖者不能私訊、不能加好友，也不能重新建立 direct conversation。
- 解除封鎖不自動恢復好友關係。
- 後端每次好友、封鎖與訊息操作都重新檢查權限，前端隱藏不是安全邊界。

## 建議架構

採用單一 direct conversation 架構：

```text
使用者 A ─┐
          ├─ Conversation(kind=direct) ─ Message...
使用者 B ─┘

分類 = 目前雙方是否為 Friendship
```

不將私訊和好友聊天拆成兩個聊天室，避免歷史搬移、重複聊天室與訊息遺失風險。現有 `Conversation`、`ConversationMember`、`Message` 模型延伸使用，飯局聊天室維持原有流程。

## 資料模型

### Friendship

新增雙向好友關係表，以排序後的 `user_low_id`、`user_high_id` 作為唯一主鍵或唯一約束，避免 A-B 與 B-A 重複保存。

### FriendRequest

新增好友邀請表，保存 requester、recipient、status、created_at、responded_at。有效的 pending 邀請同一方向不可重複；接受後建立 Friendship。

### Block

新增封鎖表，保存 blocker、blocked、created_at，以兩個使用者組合做唯一約束。封鎖操作在同一交易中清除好友關係與未完成邀請。

### UserProfile

新增 `accept_stranger_messages`，預設為 `true`，由個人設定頁修改。

### Direct conversation

第一次私訊時建立一對一 `Conversation(kind="direct")` 與兩筆 ConversationMember。服務層必須以兩個使用者的 canonical pair 查找既有聊天室，並在交易中避免重複建立。

## API 與 WebSocket

### REST

- `GET /api/v1/conversations?kind=direct|friends|meal`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/friend-requests`
- `POST /api/v1/friend-requests/{id}/accept`
- `POST /api/v1/friend-requests/{id}/reject`
- `POST /api/v1/friend-requests/{id}/cancel`
- `DELETE /api/v1/friends/{user_id}`
- `POST /api/v1/blocks/{user_id}`
- `DELETE /api/v1/blocks/{user_id}`
- 個人資料端點提供好友、邀請、封鎖及私訊操作所需的 relationship state。
- 個人設定端點提供 `accept_stranger_messages`。

REST 負責初始資料、歷史訊息分頁、好友／封鎖關係變更及斷線補資料。

### WebSocket

沿用單一 `/api/v1/ws`：

- `subscribe` 支援 `conversation_id`。
- `message.send` 支援 `conversation_id`。
- 成功保存後推送 `message.created`，再回傳 ack。
- 新訊息推送 `conversation.updated`，讓聊天列表重新載入最新摘要與分類。
- 好友邀請、接受、拒絕、取消、解除好友、封鎖與解除封鎖推送 `social.updated` 給相關使用者。
- 事件只傳遞給有權限的使用者；受眾欄位是伺服器內部路由資料，不送到瀏覽器。
- Redis 只作跨 API instance 的事件傳輸，PostgreSQL 仍是訊息與關係的權威資料來源。

## 前端流程

- `/chat` 啟用「私訊｜好友｜約飯」三個分頁。
- 私訊與好友列表使用同一個 conversation row component；分類由後端回傳。
- 點擊私訊／好友列表後進入共用 direct chat panel。
- 個人頁顯示加好友、邀請狀態、接受／拒絕、好友、發送私訊、封鎖／解除封鎖等操作狀態。
- 設定頁加入接受陌生人私訊開關。
- 送出訊息採 server-confirmed flow：先保存，收到 `message.created` 後顯示，不做無法回滾的假成功。
- 錯誤、被封鎖、拒絕陌生人私訊與好友邀請狀態都顯示可理解的 UI feedback。

## 訊息捲動實作

聊天室元件需維護：

- `scroll container ref`
- `isNearBottom`
- `unreadIncomingCount`
- 載入前後的 `scrollHeight`／anchor offset

收到訊息時先記錄更新前是否接近底部，再更新排序後的訊息陣列；DOM 更新後只有在原本接近底部時才捲到底，否則增加新訊息提示數。插入較早頁面時以 `newScrollHeight - oldScrollHeight` 補回 `scrollTop`。

## 安全與錯誤處理

- 好友、私訊、封鎖及 conversation access 每次由後端依目前資料庫狀態檢查。
- 所有訊息仍套用內容長度、空白內容與一般頻率限制。
- 陌生人第一則訊息限制必須由後端判定，不能只在前端禁用按鈕。
- 同一對使用者建立 direct conversation 時處理競態，避免重複聊天室。
- WebSocket 斷線後由 REST 重新載入 conversation 與訊息歷史。
- 被封鎖或解除好友後，既有 WebSocket subscription 必須停止後續訊息讀寫。

## 測試與驗收

### Backend

- migration 可升級與降級。
- 好友邀請完整狀態轉換與重複邀請防護。
- 成為好友後沿用相同 conversation id。
- 陌生人第一則、收件者回覆、拒絕陌生人訊息。
- 封鎖後不能私訊／加好友，解除封鎖不自動恢復好友。
- WebSocket message persistence、authorization、social.updated 與 direct conversation event。

### Frontend

- 訊息新增永遠按時間順序出現在底部。
- 靠近底部會自動捲動；閱讀歷史時只顯示新訊息提示。
- 載入舊訊息不改變目前閱讀位置。
- 私訊／好友／約飯分頁與列表分類正確。
- 個人頁、設定頁的好友／私訊／封鎖操作回饋正確。
- 桌面與手機 viewport 均可完成聊天流程。

### 明確排除

- 圖片訊息。
- 已讀狀態。
- 輸入中提示。
- 訊息收回。
- 追蹤與檢舉的完整流程。
