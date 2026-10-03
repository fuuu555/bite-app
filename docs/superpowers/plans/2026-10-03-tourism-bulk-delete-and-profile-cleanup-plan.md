# 觀光署批次刪除與個人頁精簡實作計畫

依據 `docs/superpowers/specs/2026-10-03-tourism-bulk-delete-and-profile-cleanup-design.md`。

## 工作項目

- [x] 後端新增原子批次刪除服務／管理 API：最多 100 筆 ID、依資料集排序取得匯入鎖、寫入 tombstone 並刪除來源列；同步刪除單筆沿用相同服務。
- [x] 後端測試批次成功、重複／不存在 ID、同批回滾、tombstone 與重匯抑制。
- [x] 前端疑似重複頁加上單筆勾選、已選數量、批次確認清單；篩選或翻頁清空選取；成功一次呼叫並重新載入一次。
- [x] 個人設定移除登入裝置區塊與 `/me/sessions` 載入／撤銷狀態；不變更後端 session API。
- [x] 內建頭貼隱藏可見名稱，補上 `aria-label`，保留鍵盤與選取語意。
- [x] 執行後端／前端測試、lint 與 typecheck，確認 migration／既有變更未被改壞。

## 驗證結果

- Backend: 19 passed, 15 skipped; Ruff passed.
- Tourism DB integration (PostGIS enabled): 7 passed.
- Frontend: typecheck and ESLint passed; 27 tests passed.
