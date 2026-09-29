# E2E tests / E2E 測試

Playwright tests cover browser-level acceptance flows.
Playwright 測試負責瀏覽器層級的驗收流程。

Run the list check without starting a browser:

```powershell
pnpm exec playwright test --list
```

Run all browser tests:

```powershell
pnpm test:e2e
```

The admin flow runs only when `E2E_ADMIN_EMAIL` and `E2E_ADMIN_PASSWORD` point to a dedicated test account. It is skipped locally when either value is missing, so the suite never changes an existing administrator account.
管理員流程只會在 `E2E_ADMIN_EMAIL` 與 `E2E_ADMIN_PASSWORD` 指向專用測試帳戶時執行；本機缺少任一設定時會略過，不會修改既有管理員帳戶。

Run the application shell and public map acceptance tests:

```powershell
pnpm exec playwright test tests/e2e/app-shell.spec.ts tests/e2e/public-map.spec.ts
```

Run all static analysis, unit tests, and builds from the repository root:

```powershell
pnpm check:quality
```

Run map search and filter browser tests:

```powershell
pnpm exec playwright test tests/e2e/map-search-filters.spec.ts
```

Public map tests intercept the map API in memory and do not create database rows.
公開地圖測試會在瀏覽器內攔截地圖 API，不會在資料庫留下測試資料。

Map search tests also intercept search, cuisine, and public map APIs in memory.
地圖搜尋測試同樣會在瀏覽器內攔截搜尋、料理分類與公開地圖 API。

To preview the temporary map clustering demo, open `/map?cluster-demo=1` or use the admin sidebar quick link「群聚展示」.
要預覽暫時性的地圖群聚展示，可開啟 `/map?cluster-demo=1`，或使用管理後台側邊的「群聚展示」快速鍵。
