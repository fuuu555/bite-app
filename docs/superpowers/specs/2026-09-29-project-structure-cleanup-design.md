# 專案命名與資料夾整理設計

## 目標

讓測試、程式碼與 README 直接以功能命名，移除開發階段編號造成的閱讀負擔，並用少量穩定分類整理前端元件。

## 命名

- E2E 測試改用 `app-shell`、`admin`、`public-map`、`map-search-filters`、`explore`、`user-account` 等功能名稱。
- 品質檢查 scripts 改為 `check:quality` 與 `check:all`，不再依開發階段串接。
- 原始碼 docstring、CSS 註解、測試資料與使用者文案直接描述功能。
- `DEVELOPMENT_PLAN.md` 的階段規劃與已套用的 Alembic revision ID 保留；修改 revision 名稱會破壞 migration 歷史。

## 前端資料夾

`components` 只整理成三個功能群組：

- `components/admin`：管理後台、店家與料理管理元件。
- `components/map`：公開地圖、搜尋控制與店家預覽。
- `components/user`：登入、探索、個人頁、餐廳詳細頁與使用者導覽。

`lib` 目前檔案數量少且名稱清楚，維持扁平；後端已依 `core`、`domain`、`integrations`、`routers`、`services`、`scripts` 分層，不再增加子資料夾。

## 清理

- 刪除未被引用的 Next.js 預設 SVG。
- 只刪除能由引用搜尋與建置驗證確認的孤兒程式或樣式。
- 保留產品規劃中的準備中路由與 placeholder，不把尚未完成功能誤判成死碼。

## 驗證

- 全專案搜尋不再出現舊 E2E 檔名與 `check:stage*` scripts。
- README 專案樹與實際路徑一致。
- Frontend format、lint、typecheck、unit tests、production build 通過。
- Backend lint、typecheck、tests 通過。
- Playwright 能列出並執行重新命名後的 E2E 測試。
