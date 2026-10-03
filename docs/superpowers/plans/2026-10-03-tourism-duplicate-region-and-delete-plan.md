# 觀光署疑似重複地區篩選與永久刪除實作計畫

依據 `docs/superpowers/specs/2026-10-03-tourism-duplicate-region-and-delete-design.md`。

## 工作項目

- [x] 新增 migration：tombstone table；移除 `is_ignored` 欄位。
- [x] 匯入時略過 tombstone 中的來源 ID；永久刪除來源列並在同一交易寫入 tombstone。
- [x] 疑似配對 API 支援 city／district 篩選；管理員刪除 API 僅刪來源列，不影響 BiteMap 店家。
- [x] 管理介面疑似重複頁加入縣市、行政區篩選與刪除確認；移除已忽略、忽略、還原 UI。
- [x] 更新後端及前端測試；跑全套相關測試、ruff、eslint、typecheck、migration 檢查。

## 驗證結果

- 後端一般測試：18 passed、14 skipped；另外兩個 PostGIS 整合測試已以隔離隨機資料執行，均通過。
- 前端測試：27 passed；TypeScript、相關 ESLint 與後端相關 Ruff 通過。
- 本機 Alembic revision 已升至 `0030_tourism_source_deletions`。
