# README 與前端目錄結構整理設計

## 目標

讓剛取得 BiteMap 專案的開發者，可以從 README 快速理解前端路由、功能模組、共用程式與 API 的責任邊界；同時移除前端重構後留下的空遺留目錄。

## 範圍

- 更新 `README.MD` 的「專案結構」，以目前實際的 `apps/frontend/src/app`、`features`、`shared` 與 `styles` 為準。
- 在 README 說明 `app` 只負責路由組合、`features` 依產品功能分組、`shared` 放跨功能共用程式。
- 保留目前實際被使用的檔案與目錄，不進行功能搬遷或路由調整。
- 只刪除已確認為空且沒有 import／設定引用的舊目錄：`apps/frontend/src/components` 與 `apps/frontend/src/lib`。

## 不在範圍

- 不刪除仍有路由或程式引用的頁面／元件，例如 `register` 與 `coming-soon`。
- 不修改 API、資料庫、環境變數、啟動流程或產品功能。
- 不將 `features` 再拆成更細的資料夾；目前的 `api`、`components`、`utils` 分層已足夠清楚。

## README 結構呈現

README 會以樹狀圖呈現主要入口，並在圖後補充新人閱讀順序：先看根目錄啟動文件，再看 route `app`，接著看對應 feature，最後查看 shared 與 API client。後端、packages、tests、docs 與設定檔只列出新人需要知道的主要用途。

## 驗收

- README 不再列出已不存在的 `src/components` 與 `src/lib`。
- README 列出的前端主要目錄與實際檔案結構一致。
- 空遺留目錄不存在，且所有 TypeScript import 仍解析到現有路徑。
- README 相關文件檢查、前端 typecheck 與測試通過。
