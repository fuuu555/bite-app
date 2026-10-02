# Stage 8 WebSocket、約飯即時同步與群組聊天室實作計畫

## 目標

完成 Stage 8 第一批：建立可跨 API instance 的 WebSocket 事件基礎，將約飯固定輪詢改成事件觸發更新，並提供有持久歷史與嚴格成員權限的純文字約飯聊天室。

## 工作 1：資料模型與可逆 Migration

- 新增 `Conversation`、`ConversationMember`、`Message` 模型及關聯。
- 新增可逆 Alembic migration，建立唯一限制、索引及既有飯局聊天室回填。
- 新增聊天回應 schema 與游標分頁契約。
- 驗證：migration upgrade／downgrade 測試、模型限制測試、backend typecheck。

## 工作 2：聊天室 REST 服務

- 新增飯局聊天室查找、成員同步、訊息讀取及聊天列表 service。
- 新增 `GET /api/v1/meals/{meal_id}/messages` 與 `GET /api/v1/conversations?kind=meal`。
- 所有讀取以目前 `meal_memberships` 狀態執行後端授權。
- 驗證：正式成員成功，pending／left／removed／非成員拒絕，游標排序穩定。

## 工作 3：WebSocket 與事件匯流排

- 加入 Redis async client、設定與 Docker Compose 服務。
- 建立本機連線管理器、Redis Pub/Sub bridge 與測試用記憶體模式。
- 新增 `/api/v1/ws`，使用 Session Cookie 與 Origin allowlist 驗證。
- 實作 subscribe／unsubscribe／message.send／ping，以及 ready／ack／error／meal.updated／message.created／pong。
- 加入訊息長度與連線內頻率限制；訊息提交後才廣播。
- 驗證：認證、Origin、訂閱權限、訊息持久化、錯誤封裝及撤權測試。

## 工作 4：約飯事件整合

- 在建立、加入、退出、取消、審核、移除、候選異動、開始投票、投票及結算成功提交後發布 `meal.updated`。
- 公開狀態、私人申請者狀態與正式成員聊天訂閱分開授權。
- 退出、移除及取消時主動重新檢查並撤銷聊天訂閱。
- 驗證：每個 mutation 的事件測試、非正式成員不取得票數或聊天事件。

## 工作 5：OpenAPI Client 與前端連線層

- 重新產生 OpenAPI TypeScript Client。
- 建立單一 WebSocket Provider、事件型別、訂閱生命週期、心跳及指數退避重連。
- 新增訊息與聊天列表 REST client。
- 驗證：前端單元測試涵蓋連線、去重、重連、訂閱與安全錯誤。

## 工作 6：約飯頁與聊天室 UI

- 約飯列表與詳情收到 `meal.updated` 後重新讀取 REST，移除 10 秒／3 秒固定輪詢。
- 在飯局詳情加入正式成員聊天室、歷史向上分頁、發送及重試狀態。
- `/chat` 啟用約飯聊天室列表；私訊與好友保留後續開放說明。
- 驗證：loading、empty、error、retry、手機與桌面版測試。

## 工作 7：完整驗證與文件

- 執行 backend formatter、lint、typecheck、migration 與測試。
- 執行 frontend formatter、lint、typecheck、單元測試與 production build。
- 執行約飯聊天室及退出撤權 E2E。
- 更新 README 的 Redis、環境變數、WebSocket 啟動與測試說明。
- 確認需求文件、開發計畫與實作一致，不包含假資料或權限繞過。
