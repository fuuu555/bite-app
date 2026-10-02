# 好友頁社交中心、聊天室導覽與訊息排序設計

日期：2026-10-02  
狀態：已由使用者確認，進入 implementation plan

## 背景

Stage 8 第一批已完成約飯聊天室、WebSocket、Redis Pub/Sub、好友關係、私訊與基本訊息捲動。驗收時仍發現聊天畫面偶爾沒有依實際建立順序排列；同時目前 `/chat` 把「私訊／好友／約飯」放在同一層，好友管理入口不夠清楚。

本批將修正訊息排序，重新整理好友與聊天室的資訊架構，並加入每位使用者可分享的 6 位數好友碼。圖片、已讀、輸入中提示與訊息收回仍不在本批範圍。

## 已確認的產品決策

### 1. 好友頁是社交中心

個人頁原本第一個「公開資料」分頁改為「好友」。頭像、名稱、簡介與 Tag 仍保留在個人頁上方，不會因分頁更名而消失。

好友頁集中以下功能：

- 顯示目前使用者的好友碼。
- 複製自己的好友碼。
- 輸入對方好友碼並搜尋使用者。
- 從搜尋結果送出好友邀請。
- 查看待處理好友邀請。
- 查看好友名單。
- 接受、拒絕、取消好友邀請與解除好友。
- 從好友列前往對應的聊天。
- 設定是否接受陌生人的第一則私訊。

好友頁只顯示精簡好友列表與必要入口；完整訊息列表不放在好友頁。

### 2. 聊天室負責訊息

Footer 與頁面標題使用「聊天室」，原本的「私訊」命名移除。

聊天室頁首只顯示「聊天室」，移除副標「和即將一起吃飯的人，把細節聊清楚」。

聊天室至少有兩個分類：

- `私聊`：雙方目前不是好友的 direct conversation。
- `好友聊`：雙方目前是好友的同一個 direct conversation。

好友關係變更只影響分類，不建立新 conversation，也不搬移歷史訊息。原本私聊成為好友後，會從「私聊」移到「好友聊」；解除好友後回到「私聊」。

約飯聊天室仍是飯局成員的群組聊天室，只允許正式飯局成員讀寫。它不會出現在好友名單，也不會被當成好友聊天；主要入口維持約飯詳細頁的聊天室區塊。為避免導航歧義，本批聊天室主頁只呈現 `私聊` 與 `好友聊` 兩類；既有約飯聊天 API、WebSocket 訂閱與 `/meals/{mealId}#chat` 深連結保留。

### 3. 6 位數好友碼

每位使用者建立一組穩定、唯一的 6 位數好友碼，允許前導零。好友碼用途只有查找使用者並送出好友邀請，不是登入密碼、Session token 或授權憑證。

好友碼只在自己的好友頁顯示，公開個人頁不顯示。第一批不提供重新產生好友碼功能，避免分享後失效與好友關係混亂。

好友碼搜尋必須：

- 要求有效登入。
- 僅接受精確 6 位 ASCII 數字。
- 回傳最小必要的公開資料與目前 relationship state。
- 仍需要送出並接受好友邀請，不能因查到 code 直接成為好友。
- 套用使用者與來源的查詢頻率限制，避免 6 位碼被大量枚舉。
- 對不存在、被封鎖或不可用的帳號回傳不洩漏敏感資訊的結果。

### 4. 陌生人私訊設定

`accept_stranger_messages` 維持既有資料與後端政策，預設為 `true`。前端控制項從個人設定表單移到好友頁的「社交隱私」區塊：

- 開啟：陌生人可以傳第一則訊息，仍遵守一則待回覆限制。
- 關閉：非好友不能建立新的私聊；好友聊天不受影響。
- 後端每次建立 direct conversation 與發送訊息仍重新檢查，前端開關不是安全邊界。

## 訊息排序與捲動

### 排序規則

歷史訊息、WebSocket 新訊息與重新連線補資料合併後，都使用同一個升冪 comparator；目前訊息採 server-confirmed flow，不建立未確認的 optimistic 訊息：

```text
(server_created_at ASC, message_id ASC)
```

`message_id` 只作同一時間戳的 deterministic tie-breaker，不依賴 WebSocket 抵達順序、陣列 push 順序或前端產生時間。後端歷史查詢、列表最新訊息與前端顯示必須遵守同一個順序語意。

新訊息固定出現在訊息列表底部。初次載入完成後定位到底部；使用者接近底部時收到新訊息會跟隨到底部；使用者往上閱讀時不跳動，改累計「N 則新訊息」；載入較早訊息時以 scroll height 差值保留 anchor。

### 驗收條件

- 亂序抵達的訊息最後仍依 server timestamp 與 ID 顯示。
- 同時間戳的訊息每次重新整理後順序一致。
- 歷史分頁與即時訊息合併不重複、不插錯位置。
- 手機與桌面版新訊息均出現在最下方。

## 資料模型與 migration

### UserProfile

在 `user_profiles` 新增：

- `friend_code`: `String(6)` 固定長度字串，內容限定為 ASCII 數字。
- `NOT NULL`。
- 唯一索引。

資料庫層加上 6 位數格式 CheckConstraint，服務層也必須做同樣驗證；`String(6)` 保留前導零，不轉成 integer。

建立新 profile 時由後端使用安全亂數產生 6 位數字，遇到唯一衝突時重試；不可由前端產生。既有 profile migration 需要以同樣規則回填且通過唯一約束，再切換為 non-null。migration 必須可逆；降級前需要明確處理回填欄位與唯一索引。

Friendship、FriendRequest、Block、Conversation、DirectConversationPair、Message 不新增重複關係欄位，沿用現有正規化模型。

## API 設計

### 既有 API 調整

- `MyProfileResponse` 增加目前使用者自己的 `friend_code`。
- `PublicProfileResponse` 不回傳 `friend_code`。
- `PATCH /api/v1/me/profile` 保留更新 `accept_stranger_messages` 的能力；好友頁使用此 API 更新開關。
- `GET /api/v1/conversations?kind=direct` 與 `kind=friends` 的資料契約保持不變，前端只調整顯示名稱。

### 新增 API

- `GET /api/v1/friends`：列出目前使用者的有效好友，依雙方關係建立時間與穩定 ID 排序，回傳好友最小必要 profile 摘要與可進入的 canonical conversation ID（若已建立）。
- `GET /api/v1/users/lookup?friend_code=123456`：以好友碼查找一位可互動使用者，回傳最小 profile 摘要與 relationship state；不得回傳使用者 email、好友碼或不必要的帳號欄位。

既有好友邀請端點繼續處理送出、接受、拒絕、取消；既有封鎖端點繼續處理封鎖與解除封鎖。好友頁可以並行載入好友列表、待處理邀請與自己的 profile，但所有 mutation 都由後端重新驗證。

修改 API 後同步產生 `packages/api-client/src/schema.d.ts` 與相關 client 型別。

## 前端結構

### 個人頁

`ProfilePage` 的第一個 tab 由 `overview` 改為 `friends`，其餘 `reviews` 與 `favorites` 保留。好友區塊建議拆成小型元件，分別負責：

- `FriendCodeCard`：顯示與複製自己的 code、好友碼搜尋。
- `FriendRequestsPanel`：顯示 incoming／outgoing pending request 與操作。
- `FriendList`：顯示好友摘要與「前往聊天室」入口。
- `SocialPrivacyPanel`：切換 `accept_stranger_messages`。

載入失敗時，各區塊需要顯示可理解錯誤；好友列表為空時顯示搜尋好友的入口，不讓整頁變成空白。好友碼查詢結果只暫存在當前頁面狀態，不把查詢碼寫進 URL 或公開 profile。

### 聊天室

`ChatPage` 標題維持「聊天室」，分類顯示名稱改為：

- backend category `direct` → `私聊`。
- backend category `friends` → `好友聊`。

category URL 值保持既有英文值，避免既有深連結失效。每一類共用 conversation row 與 `ConversationChatPanel`；好友頁進入聊天時直接帶入 canonical conversation ID。約飯聊天室不併入好友列表，仍從飯局詳細頁載入 meal conversation。

聊天室主頁預設分類改為 `direct`（畫面顯示「私聊」），不再預設載入約飯分類；既有約飯詳細頁深連結與 meal API 不受影響。

### 設定頁

移除個人設定表單中重複的「接受陌生人私訊」控制項，避免同一個設定在兩個入口產生不一致；公開資料編輯仍保留名稱、簡介、頭像與 Tag。

## 即時事件與權限

- 好友邀請、接受、拒絕、取消、解除好友、封鎖與解除封鎖仍以 `social.updated` 通知相關使用者。
- 好友頁在收到 social event 後重新載入好友、邀請與 relationship state。
- 聊天列表收到 `conversation.updated` 後重新載入目前 category；好友關係變更造成分類改變時，不能建立第二個 direct conversation。
- 約飯成員離開、被移除或失去資格後，既有 meal WebSocket subscription 立即失效；這套權限與好友頁完全分離。
- 所有 API 與 WebSocket subscription 都以後端資料庫狀態為準，不能只靠前端 tab 隱藏。

## 測試與驗收

### Backend

- migration 升級與降級。
- 新 profile 產生唯一 6 位好友碼，前導零可用；既有 profile 回填且無重複。
- 好友碼精確查詢、格式驗證、未知 code、停用帳號與封鎖狀態。
- 好友列表只回傳目前使用者的有效好友；好友邀請狀態變更後列表與 relationship state 一致。
- `accept_stranger_messages` 開關對陌生人第一則私訊生效，好友不受影響。
- 好友成立與解除沿用相同 direct conversation ID。
- 約飯非正式成員不能取得 meal conversation，且不會出現在 direct/friends 列表。
- WebSocket 與 REST 訊息排序使用 server timestamp＋message ID，亂序事件最後仍正確排列。

### Frontend

- 個人頁第一個 tab 顯示好友頁，公開資料仍保留在頁首。
- 好友碼複製、搜尋、送出邀請、接受／拒絕／解除與前往聊天室。
- 陌生人私訊開關只在好友頁出現，設定成功後重新整理仍維持狀態。
- 聊天室顯示「私聊／好友聊」，不再顯示「私訊」作為分類名稱。
- 約飯聊天室仍可從約飯詳細頁開啟，且不會出現在好友名單。
- 歷史與即時訊息在桌面／手機均依 server timestamp＋ID 升冪排列，新訊息固定在底部。
- 閱讀歷史時保留 scroll anchor，靠近底部時自動跟隨，離開底部時顯示新訊息提示。

### 明確排除

- 圖片訊息。
- 已讀狀態。
- 輸入中提示。
- 訊息收回。
- 好友碼重新產生。
- 追蹤與檢舉的完整流程。

## 風險與取捨

6 位數 code 的搜尋空間有限，因此不能拿來作認證；查詢必須登入、限流且只回傳最小資料。把 code 放在好友頁而非公開個人頁，可降低被公開枚舉的機會，但使用者仍需主動分享自己的 code。

把好友管理與聊天分開，可以降低個人頁與約飯頁的擁擠程度，也讓「關係」與「訊息」有清楚責任邊界；代價是使用者從好友名單進入聊天需要一次點擊。約飯聊天保留在飯局上下文，能避免非成員誤解為好友聊天，但使用者不能在好友頁直接看到飯局群組，這是刻意的權限與資訊分層。
