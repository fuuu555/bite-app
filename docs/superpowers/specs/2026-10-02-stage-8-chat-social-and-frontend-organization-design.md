# Stage 8 聊天互動、追蹤與前端功能導向整理設計

日期：2026-10-02  
狀態：待使用者審閱

## 目標與範圍

本批在既有 WebSocket／Redis、約飯聊天室、好友與私聊基礎上，完成以下功能：

1. 已讀狀態。
2. 輸入中提示。
3. 訊息收回。
4. 追蹤與取消追蹤。
5. 同飯局成員互相封鎖後，仍保留飯局成員與飯局群聊權限。
6. 將前端使用者功能整理成清楚的功能導向資料夾。

圖片訊息明確排除在本批之外，不新增附件欄位、檔案上傳或物件儲存流程。

## 已確認的產品規則

### 同飯局封鎖

- 同一飯局中的兩位成員互相封鎖後，雙方仍保留原本的飯局成員資格。
- 雙方仍可查看及發送該飯局群聊訊息。
- 封鎖只限制私聊、好友聊、追蹤與個人頁互動。
- 封鎖不自動讓任何一方退出飯局，也不改變投票資格。
- 若其中一方退出或被移除，仍依既有飯局成員權限撤銷群聊權限。

### 訊息收回

- 只有訊息作者可以收回自己的訊息。
- 送出後 2 分鐘內可以收回；超過時間由後端拒絕。
- 收回保留原訊息資料與稽核時間，不硬刪除資料。
- 歷史訊息與即時事件都顯示「訊息已收回」，不再顯示原文字。

### 追蹤

- 追蹤是單向關係，不會自動成為好友。
- 追蹤不會自動取得私聊權限，私聊仍遵守陌生人私訊設定與首則限制。
- 公開個人頁提供追蹤／取消追蹤。
- 個人頁社交中心提供追蹤中與追蹤者列表。
- 封鎖時清除雙方的追蹤關係；解除封鎖不自動恢復追蹤。

## 前端功能導向整理

### 原則

保留 Next.js App Router 的路由位置與 URL，不把路由檔案搬成一般元件。每個 `page.tsx` 只負責匯入並組裝功能頁，實際畫面與狀態移到 `src/features`。

使用者 Footer 的五個入口各自有明確的功能資料夾：

```text
apps/frontend/src/
├─ app/                         # 只保留路由、layout、loading、error
├─ features/
│  ├─ home/                     # Footer 首頁／探索
│  ├─ map/                      # Footer 地圖
│  ├─ meals/                    # Footer 約飯、投票、約飯聊天
│  ├─ chat/                     # Footer 聊天室、私聊、好友聊
│  ├─ profile/                  # Footer 個人頁、好友社交中心、設定
│  ├─ restaurants/              # 餐廳詳細頁與留言互動
│  └─ admin/                    # 管理後台功能，維持獨立邊界
├─ shared/
│  ├─ ui/                       # 確認框等跨功能 UI
│  ├─ auth/                     # 使用者登入門禁與 Session 輔助
│  └─ realtime/                 # 共用 WebSocket Provider／事件型別
└─ lib/                         # 逐步移除；只保留真正跨功能的低階工具
```

每個功能內依需要使用以下子資料夾，不為單一檔案強行建立空資料夾：

```text
features/chat/
├─ components/                  # 聊天列表、訊息面板、輸入列
├─ hooks/                       # 捲動、已讀、輸入中狀態
├─ api/                         # 聊天 REST client
├─ types/                       # 聊天 DTO 與事件型別
└─ index.ts                     # 對外公開的少量組裝入口
```

目前 `components/user` 的聊天室、約飯、個人頁與餐廳元件依責任搬到對應功能資料夾；管理後台不與使用者功能混放。搬移期間保留必要的 re-export，完成後移除重複入口與孤兒 import。此重整不改路由 URL、API URL 或視覺行為。

## 已讀狀態設計

### 資料模型

在 `conversation_members` 增加目前使用者的閱讀游標：

- `last_read_message_id`：最後已讀訊息 ID，可為空。
- `last_read_at`：伺服器確認時間。
- 仍以 `(created_at, id)` 作為訊息排序與游標比較，不依賴 WebSocket 抵達順序。

這是每個使用者對每個聊天室的一個游標，不建立每則訊息一筆 read receipt。更新時由後端確認訊息屬於該 conversation，且不可把閱讀游標倒退。

### REST／WebSocket

- `POST /api/v1/conversations/{conversation_id}/read`：斷線或頁面初始化時可補送已讀游標。
- WebSocket 命令 `conversation.read`：攜帶 `conversation_id` 與 `message_id`。
- WebSocket 事件 `conversation.read`：只推送給同聊天室且有權限的成員。
- 歷史訊息與聊天列表回傳目前使用者的 unread count／read cursor。

前端進入聊天室並看到最新訊息、或使用者滾到底部時，將目前最後一則可見訊息標記為已讀。閱讀歷史時不把尚未看見的最新訊息誤標為已讀。私聊／好友聊顯示對方是否已讀；約飯群聊先提供每位成員的閱讀游標給未來擴充，但本批只顯示聊天室未讀狀態，不做複雜的逐人 UI。

## 輸入中提示設計

- WebSocket 命令：`typing.start`、`typing.stop`。
- WebSocket 事件：`typing.updated`，只傳送使用者顯示名稱與目前輸入狀態，不保存資料庫。
- 前端輸入變更採 debounce，停止輸入或離開聊天室時送出 `typing.stop`。
- 後端與前端都設逾時清除，避免瀏覽器關閉或斷線後留下永久「輸入中」。
- 事件必須套用聊天室權限；沒有私聊權限者不能觀察或發送輸入中事件。
- 不在輸入中事件中傳送文字內容。

## 訊息收回設計

- WebSocket 命令：`message.recall`，攜帶 conversation 與 message ID。
- 後端在交易中確認作者、訊息尚未收回、訊息仍在 2 分鐘期限內，設定 `recalled_at`。
- WebSocket 事件：`message.recalled`，只攜帶訊息 ID、收回時間與必要的 conversation ID。
- REST 歷史資料對已收回訊息回傳 `is_recalled=true`，並隱藏原始內容。
- 其他成員收到事件後將原訊息替換成「訊息已收回」；發送者也必須以相同資料重繪，避免兩端狀態不同。
- 超過期限、非作者、非聊天室成員或已收回訊息再次操作，回傳可理解的錯誤。

## 追蹤資料與 API

新增正規化 `user_follows` 關聯表：

- `follower_id`、`followed_id`、`created_at`。
- `follower_id <> followed_id`。
- `(follower_id, followed_id)` 唯一約束。

REST 端點：

- `POST /api/v1/users/{user_id}/follow`
- `DELETE /api/v1/users/{user_id}/follow`
- `GET /api/v1/me/following`
- `GET /api/v1/me/followers`
- 個人資料回應提供目前使用者的 `follow_status`，供公開個人頁顯示正確操作狀態。

追蹤與取消追蹤成功後，透過既有 `social.updated` WebSocket 事件更新相關使用者的個人頁與社交中心。封鎖交易同時移除好友、未完成邀請與追蹤關係；飯局成員關係不移除。

## WebSocket 事件與權限

事件流程維持「資料庫成功提交後才廣播」：

```text
client command
  → session／conversation／meal policy 檢查
  → PostgreSQL transaction（若需要）
  → Redis Pub/Sub
  → 有權限的 WebSocket clients
```

- `conversation.read` 只更新自己的閱讀游標，但事件可通知同聊天室成員。
- `typing.*` 是短暫事件，不進 Redis 歷史、不進 PostgreSQL。
- `message.recall` 必須保存後才發布 `message.recalled`。
- `follow`、`unfollow` 與封鎖沿用既有社交 Policy。
- 飯局聊天室授權只依正式飯局成員狀態；同飯局封鎖不阻擋群聊。
- 私聊／好友聊仍依封鎖、好友與陌生人首則訊息規則判定。

## 測試與驗收

### 前端整理

- 五個 Footer 入口各有對應 `features` 資料夾。
- 路由 URL 與頁面可正常載入，`page.tsx` 不再承擔大型頁面實作。
- 搬移後無循環 import、未使用 import 或重複功能入口。
- 前端 formatter、lint、typecheck、production build 與主要 E2E 通過。

### 已讀、輸入中與收回

- 已讀游標只前進、不倒退；重連後可恢復，且 unread count 正確。
- 使用者閱讀歷史時不會因新訊息被誤標已讀。
- 輸入中提示只出現在有權限的聊天室，停止輸入、離開與斷線都會清除。
- 非作者、超過 2 分鐘、已收回或無權限操作收回都被拒絕。
- 收回後重新載入歷史與即時畫面都只顯示「訊息已收回」。

### 追蹤與封鎖

- 追蹤、取消追蹤、追蹤中列表與追蹤者列表可正常使用。
- 追蹤不建立好友、不繞過陌生人私訊限制。
- 封鎖會清除好友、未完成邀請與追蹤關係，解除封鎖不自動恢復。
- 同飯局封鎖後雙方仍能留席、投票與使用飯局群聊；退出／移除後才撤銷飯局聊天室權限。

### 明確排除

- 圖片訊息、圖片上傳與 S3／Object Storage。
- 每則訊息的永久 read receipt 詳細歷史。
- 追蹤推薦、通知中心與檢舉流程。
