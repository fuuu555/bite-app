# 好友頁社交中心、聊天室導覽與訊息排序實作計畫

設計規格：[2026-10-02-friends-hub-chat-navigation-and-message-order-design.md](../specs/2026-10-02-friends-hub-chat-navigation-and-message-order-design.md)

## 目標

完成已確認的 Stage 8 後續批次：

1. 修正歷史／WebSocket 訊息合併後的 deterministic 排序與底部捲動。
2. 將個人頁第一個分頁改為好友社交中心。
3. 為每位使用者建立穩定唯一的 6 位數好友碼，支援查找與送出好友邀請。
4. 將陌生人私訊開關移到好友頁。
5. 將「私訊」分類改為「私聊」，「好友」分類改為「好友聊」；約飯群組維持飯局詳細頁入口。
6. 移除聊天室頁首副標，只保留「聊天室」。

## 實作順序

### 1. 資料模型與 migration

修改：

- `apps/backend/src/api/domain/models.py`
- `apps/backend/src/api/services/profile.py`
- 新增 `apps/backend/migrations/versions/0018_friend_codes.py`

工作：

- 在 `UserProfile` 增加固定 6 字元的 `friend_code`。
- 加入 ASCII 數字格式 CheckConstraint 與唯一索引。
- 以安全亂數產生 code，允許前導零；建立 profile 與 migration backfill 都在唯一衝突時重試。
- migration 先以可安全回填的方式建立欄位，再補資料、唯一索引、格式約束與 non-null。
- downgrade 移除索引、約束與欄位。

驗證：migration upgrade／downgrade、既有 profile 回填無重複、新 profile 產生 code、前導零保留。

### 2. Backend schema、好友資料 API 與好友碼查詢

修改：

- `apps/backend/src/api/domain/schemas.py`
- `apps/backend/src/api/routers/auth.py`
- `apps/backend/src/api/routers/social.py`
- `apps/backend/src/api/services/profile.py`
- `apps/backend/src/api/services/social.py`

工作：

- `MyProfileResponse` 增加 `friend_code`；`PublicProfileResponse` 不輸出好友碼。
- 新增好友列表 response 與好友碼 lookup response，只回傳必要的 profile 摘要及 relationship state。
- 新增 `GET /api/v1/friends`。
- 新增 `GET /api/v1/users/lookup?friend_code=123456`，驗證精確 6 位 ASCII 數字。
- 查詢套用登入、封鎖、停用帳號與 relationship policy；不以查詢結果透露不必要的帳號存在資訊。
- 沿用既有好友邀請、封鎖與 `PATCH /me/profile` 開關 API。
- 產生／更新 OpenAPI client schema。

驗證：好友列表權限、lookup 格式／未知 code／封鎖、送出邀請、接受後列表更新、API contract。

### 3. Frontend API client 與好友社交中心

修改或新增：

- `apps/frontend/src/lib/user-api.ts`
- `apps/frontend/src/lib/social-api.ts`
- `apps/frontend/src/components/user/profile-page.tsx`
- 新增 `apps/frontend/src/components/user/friends-hub-panel.tsx`
- `apps/frontend/src/components/user/profile-settings-page.tsx`
- 對應 `apps/frontend/src/styles/web.css`、`mobile.css`

工作：

- 將 ProfilePage 第一個 tab 從 `overview` 改為 `friends`，保留 reviews／favorites。
- 建立好友碼卡片：顯示、複製、輸入好友碼、顯示查詢結果與送出邀請。
- 建立好友邀請區、精簡好友列表與前往聊天操作。
- 將 `accept_stranger_messages` 控制項移出個人設定表單，放入好友頁社交隱私區。
- 以 server response 更新 mutation 結果；失敗時保留可重試的錯誤提示。
- 空列表、無結果、已是好友、待處理邀請、被封鎖等狀態提供明確 UI。
- 保留頭像、名稱、簡介與 Tag 在個人頁上方，避免好友頁變成另一個公開 profile。

驗證：好友碼複製與查詢、邀請狀態、開關持久化、手機版不擁擠、既有留言／收藏分頁不回歸。

### 4. Chat 導覽與文案

修改：

- `apps/frontend/src/components/user/chat-page.tsx`
- `apps/frontend/src/components/user/conversation-chat-panel.tsx`
- `apps/frontend/src/lib/chat-api.ts`
- 對應 chat CSS 與測試

工作：

- 頁首移除「和即將一起吃飯的人，把細節聊清楚」，只保留「聊天室」。
- 分類顯示由「私訊／好友」改為「私聊／好友聊」；URL category 值維持 `direct`／`friends`。
- 聊天室主頁不顯示約飯分類，預設改為 `direct`；既有飯局詳細頁 `#chat` 入口與 meal API 保留。
- 好友頁進入好友聊天時沿用 canonical conversation ID，不建立新聊天室。
- direct／friends 共用列表與聊天面板，互動錯誤顯示正確分類名稱。

驗證：新舊 URL、空狀態、好友／私聊分類切換、約飯詳細頁聊天室入口。

### 5. 訊息 deterministic 排序與捲動修正

修改：

- `apps/frontend/src/components/user/conversation-chat-panel.tsx`
- 必要時 `apps/frontend/src/lib/realtime.tsx` 或 chat API 型別

工作：

- 抽出共用 comparator，以 `created_at ASC` 再以 `message.id ASC` 排序。
- 歷史分頁、WebSocket 新訊息、重新連線補資料合併後都去重並重新排序。
- 保持初次載入到底部、接近底部自動跟隨、閱讀歷史時顯示新訊息提示、載入舊訊息保留 anchor。
- 不新增未確認的 optimistic message，維持 server-confirmed flow。

驗證：亂序事件、相同 timestamp、分頁重疊、離開底部、桌面／手機 viewport。

### 6. Backend、Frontend 與 E2E 測試

新增或修改：

- `apps/backend/tests/test_social_chat_api.py`
- 必要的 backend auth/profile tests
- `apps/frontend/src/lib/*.test.ts`
- 必要的 component tests
- `tests/e2e/meal-chat.spec.ts`
- 新增好友頁／聊天室流程 E2E 測試

覆蓋：

- migration、好友碼生成／查詢、好友列表與邀請狀態。
- 陌生人私訊開關與好友例外。
- 私聊／好友聊分類與 direct conversation 沿用。
- 訊息順序、底部定位、新訊息提示、歷史 anchor。
- 約飯群聊權限與不出現在好友名單。
- desktop／mobile 主要流程。

### 7. 文件同步與品質檢查

修改：

- `FUNCTIONAL_REQUIREMENTS.md`
- `DEVELOPMENT_PLAN.md`
- 必要的 README／API client 說明

工作：

- 將已確認的好友頁、好友碼、聊天室命名與約飯聊天室邊界同步回功能需求與開發計畫。
- 不將秘密、實際好友碼或測試 token 寫入文件。
- 清理一次性探索產物，但保留正式測試與必要設計文件。

完成前執行：

- backend formatter／ruff／pyright／pytest。
- frontend prettier／eslint／typecheck／Vitest／build。
- 相關 Playwright E2E。
- `git diff`、migration 狀態與工作樹檢查。

## 不在本批實作

- 圖片訊息。
- 已讀狀態。
- 輸入中提示。
- 訊息收回。
- 好友碼重新產生。
- 追蹤與檢舉完整流程。
