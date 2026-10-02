# Stage 8 聊天互動、追蹤與前端整理實作計畫

## 目標

依據 `docs/superpowers/specs/2026-10-02-stage-8-chat-social-and-frontend-organization-design.md`，完成已讀、輸入中、訊息收回、追蹤、同飯局封鎖規則，並將使用者前端改成 `features` 功能導向結構。圖片訊息不在本批範圍。

## 執行順序

1. 盤點現有模型、migration、聊天 service/router/realtime、前端聊天與個人頁元件；先建立目前測試基線。
2. 新增 migration 與 domain model/schema：閱讀游標、訊息收回欄位、追蹤關聯表。
3. 延伸 backend service/router：已讀 REST、收回權限與期限、追蹤列表／變更、封鎖時清除追蹤。
4. 延伸 WebSocket protocol：`conversation.read`、`typing.start/stop`、`message.recall` 及對應事件，維持成功提交後才廣播。
5. 先將前端 route page 保持為薄 wrapper，再依功能搬移元件與 API：`home`、`map`、`meals`、`chat`、`profile`、`restaurants`、`shared`；逐次修正 import。
6. 更新聊天 UI：已讀標記、輸入中提示、收回操作與狀態更新；公開個人頁與好友中心加入追蹤操作與列表。
7. 補 backend／frontend／E2E 測試，執行 migration、formatter、lint、typecheck、build 與相關測試。
8. 更新 `DEVELOPMENT_PLAN.md` 與 `FUNCTIONAL_REQUIREMENTS.md` 的 Stage 8 完成／後續狀態，確認圖片訊息仍列為未完成。

## 主要驗收條件

- 閱讀游標只前進，重連後 unread count 與已讀狀態一致。
- 輸入中事件不落資料庫，離開、停止輸入與斷線會清除。
- 只有作者在兩分鐘內能收回；歷史與即時畫面都顯示「訊息已收回」。
- 追蹤不會建立好友或繞過私訊限制；封鎖會清除好友、邀請與追蹤關係。
- 同飯局封鎖不影響留席、投票或飯局群聊；退出／移除後才撤銷群聊權限。
- Footer 五個入口有各自清楚的 `features` 資料夾，路由 URL 不變。
- 圖片訊息與檔案上傳沒有被意外加入。
