# 全站內建確認框設計

## 目標

將前端所有瀏覽器原生確認框改為 BiteMap 共用的 `AppConfirmDialog`，讓使用者在同一套 App UI 中確認危險或不可逆操作。

## 涵蓋範圍

- 約飯草稿放棄：建立視窗與跨頁草稿列。
- 管理後台：刪除料理分類、刪除店家、移除菜單連結、移除照片連結。
- 已完成的約飯解除與解除好友維持共用同一元件。

## 行為

- 點擊操作按鈕只開啟確認框，不立即呼叫 API 或清除草稿。
- 取消、按 Escape 或關閉確認框不執行操作。
- 確認後沿用原本的 API、loading、成功訊息與錯誤處理。
- 危險操作使用危險色確認按鈕；草稿放棄也視為會清除資料的危險操作。

## 不在範圍

- 不修改後端 API、資料庫 schema 或權限規則。
- 不改變各操作原本的成功與失敗文字。
- 不處理非確認用途的提示文字或表單驗證錯誤。

## 驗收

- `apps/frontend/src` 不再使用 `window.confirm`、`window.alert` 或 `window.prompt`。
- 六個原生確認框入口皆改用 `AppConfirmDialog`。
- 前端 lint、typecheck、測試與 production build 通過。
