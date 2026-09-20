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

Run the Stage 2 public homepage and map acceptance tests:

```powershell
pnpm exec playwright test tests/e2e/stage0.spec.ts tests/e2e/stage2-public-map.spec.ts
```

Run the complete Stage 2 quality gate from the repository root:

```powershell
pnpm check:stage2
```

Run the complete Stage 3 map search and filter quality gate from the repository root:

```powershell
pnpm check:stage3
```

Stage 2 map tests intercept the public map API in memory and do not create database rows.
Stage 2 地圖測試會在瀏覽器內攔截公開地圖 API，不會在資料庫留下測試資料。

Stage 3 map tests also intercept search, cuisine, and public map APIs in memory.
Stage 3 地圖測試同樣會在瀏覽器內攔截搜尋、料理分類與公開地圖 API。

To preview the temporary map clustering demo, open `/map?cluster-demo=1` or use the admin sidebar quick link「群聚展示」.
要預覽暫時性的地圖群聚展示，可開啟 `/map?cluster-demo=1`，或使用管理後台側邊的「群聚展示」快速鍵。
