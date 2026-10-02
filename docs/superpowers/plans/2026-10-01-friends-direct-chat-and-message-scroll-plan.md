# Stage 8：好友、私訊與聊天室排序 Implementation Plan

> **執行備註：** writing-plans skill 在目前環境不可用；本文件依已批准的 spec 整理成可逐步執行的 implementation plan。

## 目標

在既有 Stage 8 約飯聊天室的單一 WebSocket／Redis／PostgreSQL 架構上：

1. 修正訊息新增後偶爾沒有穩定落在底部的 UI 行為。
2. 新增雙向好友邀請、接受／拒絕／取消與解除好友。
3. 新增一對一 direct conversation 私訊。
4. 加入陌生人私訊設定與第一則訊息限制。
5. 加入封鎖／解除封鎖，並讓權限立即生效。
6. 讓既有私訊在成為好友後沿用同一個 conversation 並改列於好友分類。

## 既有基礎與限制

- 後端目前已有 `Conversation(kind="meal")`、`ConversationMember`、`Message`。
- 前端目前有 `MealChatPanel`，但訊息捲動只靠列表渲染，沒有 anchor、近底偵測或新訊息提示。
- WebSocket 已支援 `meal-list`、飯局 state、飯局 chat；需向後相容，不可破壞飯局聊天室。
- 訊息永久資料來源仍是 PostgreSQL；Redis 只傳遞跨 instance 事件。
- 本計畫不包含圖片、已讀、輸入中、訊息收回、追蹤與檢舉完整流程。

## 實作步驟

### 1. 更新需求與 API 型別邊界

檔案：

- `FUNCTIONAL_REQUIREMENTS.md`
- `DEVELOPMENT_PLAN.md`
- `apps/backend/src/api/domain/schemas.py`
- `packages/api-client/src/schema.d.ts`

工作：

- 將已批准的好友、私訊、封鎖及訊息排序狀態同步到需求／開發文件。
- 把目前 meal-only 的 `MessageResponse` 泛化為 `meal_id: UUID | null`、`conversation_kind` 與 direct conversation 可用的欄位。
- 把 `MealConversationResponse` 泛化為 conversation list item，保留飯局摘要欄位的 nullable／union 語意。
- 定義 FriendRequest、Friendship、Block、RelationshipState、DirectConversation response schemas。
- 保持 OpenAPI 生成來源為 FastAPI schema，不手寫產生檔。

驗證：後端 schema import、OpenAPI 生成與 TypeScript typecheck。

### 2. 建立社交資料模型與可逆 migration

檔案：

- `apps/backend/src/api/domain/models.py`
- `apps/backend/migrations/versions/0017_social_direct_chat.py`

工作：

- 新增 `Friendship`：canonical `user_low_id`／`user_high_id`，雙使用者唯一約束與 FK。
- 新增 `FriendRequest`：requester、recipient、status、created_at、responded_at；限制同方向 pending 邀請重複。
- 新增 `Block`：blocker、blocked、created_at；canonical pair 不需要，方向有意義，兩者唯一。
- 在 `UserProfile` 增加 `accept_stranger_messages`，server default 與 ORM default 均為 `true`。
- 新增 `DirectConversationPair` mapping 表，保存 canonical 使用者 pair 到 direct conversation 的唯一映射，避免兩個平行請求產生重複聊天室；它只表達 direct conversation identity，不複製訊息或好友事實。
- 對 direct conversation 建立 pair mapping；meal conversation 不使用 mapping。
- migration downgrade 反向移除新增表、欄位與索引，不刪除既有 meal chat 資料。

驗證：migration `0017 → 0016 → 0017`，unique／FK／check constraint 整合測試。

### 3. 抽出社交 policy 與 direct chat service

檔案：

- 新增 `apps/backend/src/api/services/social.py`
- 擴充 `apps/backend/src/api/services/chat.py`
- 必要時擴充 `apps/backend/src/api/core/security.py`

工作：

- 實作 canonical pair helper、好友狀態查詢、好友邀請狀態機、封鎖查詢與 relationship state。
- 送出邀請時拒絕自己、重複 pending、已是好友及任一方向封鎖。
- 接受邀請時在同一交易內建立 Friendship，更新邀請狀態，保證冪等與雙方通知。
- 封鎖時同一交易清除 friendship 與 pending requests；解除封鎖只移除 Block。
- 實作 `ensure_direct_conversation`：檢查 Block、找 pair mapping、沒有才建立 conversation 與兩個 members。
- 實作 direct message authorization：
  - 好友可傳訊。
  - 非好友只可在收件者允許陌生人私訊時傳第一則。
  - 送件者已有訊息且收件者尚未回覆時拒絕第二則。
  - 封鎖任一方向立即拒絕。
- 一般訊息長度、空白、頻率限制沿用 meal chat 規則。
- direct conversation list 依 friendship state 分類，不複製或搬移 Message。

驗證：純 service tests 覆蓋所有 policy branches 與 direct pair concurrency／idempotency。

### 4. 擴充 REST router 與 OpenAPI

檔案：

- 新增 `apps/backend/src/api/routers/social.py`
- 擴充 `apps/backend/src/api/routers/chat.py`
- 擴充 `apps/backend/src/api/routers/auth.py` 或既有 profile router（依實際路由位置）
- `apps/backend/src/api/main.py`

工作：

- 新增好友邀請、接受、拒絕、取消、解除好友、封鎖與解除封鎖 endpoints。
- 擴充 profile response，提供目前使用者與目標使用者的 relationship state 及可用 action。
- 擴充 profile update，允許使用者修改 `accept_stranger_messages`。
- 把 `GET /conversations` 支援 `direct`、`friends`、`meal`；保留目前 `kind=meal` 使用方式的相容行為。
- 新增通用 `GET /conversations/{conversation_id}/messages`，meal 舊 endpoint 可保留為相容 wrapper 或轉呼叫通用 service。
- 所有錯誤回應使用既有安全、可理解的 HTTP status 與 detail，不洩露封鎖者資訊或私訊存在性。

驗證：HTTP integration tests、OpenAPI client 重新產生、前端 typecheck。

### 5. 擴充 Realtime protocol

檔案：

- `apps/backend/src/api/realtime.py`
- `apps/backend/src/api/routers/chat.py`
- `apps/frontend/src/lib/realtime.tsx`

工作：

- 在既有 hub 增加 conversation subscription set，保留 meal state／meal chat subscription。
- `subscribe`／`unsubscribe` 支援 `conversation_id`，每次訂閱重新檢查 membership／direct authorization。
- `message.send` 支援 `conversation_id`，先 commit 再 dispatch `message.created`，最後回 ack。
- direct message 的 audience 僅為 conversation members；封鎖或關係變更後下一次 authorization 立即失效。
- social mutation dispatch `social.updated` 給相關 user，conversation list dispatch `conversation.updated`。
- browser payload 移除 `audience_user_ids`、`source_id` 等 routing metadata。
- 前端 provider 增加 direct event types、conversation subscribe／unsubscribe 與通用 `sendMessage` payload；重連後重新訂閱。

驗證：兩個 WebSocket client 的收發、未授權訂閱、好友變更通知、斷線重連與 Redis fan-out tests。

### 6. 重構前端聊天元件與修正排序

檔案：

- 新增 `apps/frontend/src/components/user/chat-panel.tsx` 或將 `MealChatPanel` 泛化為 `ConversationChatPanel`
- `apps/frontend/src/components/user/meal-chat-panel.tsx`
- `apps/frontend/src/components/user/chat-page.tsx`
- `apps/frontend/src/lib/chat-api.ts`
- `apps/frontend/src/lib/realtime.tsx`
- `apps/frontend/src/styles/web.css`
- `apps/frontend/src/styles/mobile.css`

工作：

- 抽出 meal／direct 共用的訊息列表、composer、連線狀態與錯誤處理。
- 用升序 message array 加 stable comparator 排序；不可用 WebSocket arrival order 作為畫面順序。
- 維護 scroll container ref、near-bottom threshold、unread incoming count。
- 初始 history 完成後 scroll to bottom。
- incoming message：更新前近底才自動 scroll；不近底則保留位置並顯示提示。
- older history：以 scrollHeight delta 恢復原 anchor。
- `/chat` 啟用私訊／好友 tabs，conversation list 依 kind 查詢並可進入 selected direct conversation。
- 保持約飯聊天嵌入詳情頁的既有入口與權限行為。
- desktop／mobile 皆提供清楚的「N 則新訊息」button，避免被 footer 或 sticky action bar 遮住。

驗證：Vitest 測試 comparator／scroll decision helper；Playwright 桌面及手機測試新訊息底部、提示、舊訊息 anchor 與 direct chat。

### 7. 個人頁、設定頁與好友邀請 UI

檔案：

- `apps/frontend/src/components/user/public-profile-page.tsx`
- `apps/frontend/src/components/user/profile-page.tsx`
- `apps/frontend/src/components/user/profile-settings-page.tsx`
- `apps/frontend/src/lib/user-api.ts`
- 新增或擴充 `apps/frontend/src/lib/social-api.ts`
- 相關 app route 與 CSS

工作：

- 公開個人頁顯示加好友、邀請中、接受／拒絕、好友、發私訊、封鎖／解除封鎖。
- 設定頁提供接受陌生人私訊開關。
- 操作完成後依 REST response 更新 relationship state，並透過 `social.updated` 重新驗證。
- 所有 destructive／block action 提供可理解的確認與錯誤回饋；不在前端自行推定成功。

驗證：profile／settings component tests 與 Playwright relationship flow。

### 8. 文件、生成檔與回歸驗證

檔案：

- `FUNCTIONAL_REQUIREMENTS.md`
- `DEVELOPMENT_PLAN.md`
- `README.MD`
- `.env.example`（若新增設定）
- `packages/api-client/src/schema.d.ts`

工作：

- 記錄好友／私訊第一批完成狀態、未做功能與陌生人私訊設定。
- 重新產生 OpenAPI TypeScript schema，檢查 direct／social endpoints 存在。
- README 補充 migration、測試與 WebSocket direct chat 開發流程。
- 不加入 secrets、測試 token 或臨時 browser artifact。

## 驗證指令

```powershell
uv run --project apps/backend alembic -c apps/backend/alembic.ini downgrade 0016_stage8_meal_chat
uv run --project apps/backend alembic -c apps/backend/alembic.ini upgrade head
uv run --project apps/backend ruff check apps/backend/src apps/backend/tests
uv run --project apps/backend pyright apps/backend/src apps/backend/tests
$env:RUN_DATABASE_TESTS='1'; uv run --project apps/backend pytest -c apps/backend/pyproject.toml
pnpm --dir apps/frontend lint
pnpm --dir apps/frontend typecheck
pnpm --dir apps/frontend test
pnpm --dir apps/frontend build
pnpm exec playwright test tests/e2e/chat-social.spec.ts
```

## 完成判定

- 新訊息在飯局、好友、私訊三種聊天中都穩定出現在底部。
- 使用者閱讀歷史時不被新訊息強制捲走，能透過提示回到底部。
- 好友邀請、好友分類、私訊、陌生人限制、封鎖規則均由後端授權並有整合測試。
- direct conversation 不會重複建立，成為好友不會遺失歷史訊息。
- 桌面／手機 UI、OpenAPI client、migration、lint、typecheck、unit／integration／E2E tests 均通過。
