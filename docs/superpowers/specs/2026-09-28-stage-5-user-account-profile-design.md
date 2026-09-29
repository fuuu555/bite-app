# Stage 5 一般使用者帳號與個人頁設計

## 範圍

Stage 5 建立一般使用者的身分、Session 與基本個人資料，讓後續留言、收藏、約飯與聊天室可以共用同一套授權基礎。

本階段包含：

- 一般使用者進入 App 前必須完成 Google OIDC 登入、登出與 Session refresh。
- HttpOnly、Secure（非 development/test）、SameSite=Lax Cookie。
- Google Authorization Code Flow、state 與 PKCE；不保存 Google access／refresh token。
- 個人顯示名稱、簡介、頭像 URL 與 Tag。
- 自己的個人頁／設定頁，以及可被其他使用者查看的公開個人頁。
- 目前裝置與其他裝置的 Session 列表、單一裝置登出。
- 後端 user/admin/merchant 角色邊界；一般使用者不能呼叫管理 API。

本階段不包含留言、收藏、好友、追蹤、封鎖、檔案上傳與個人美食地圖資料規則。個人美食地圖只保留未來擴充位置，不建立來源或統計規則。

## 資料模型

- 延用 `users` 作為共用身分表；Google callback 建立 `role=user`，管理員仍使用既有 `role=admin`。
- `user_identities` 保存 Google provider subject 與 `user_id` 的唯一對照；Google 使用者不建立本地密碼。
- `user_profiles` 以 `user_id` 為主鍵，保存 `display_name`、`bio`、`avatar_url` 與建立／更新時間。
- `profile_tags` 保存系統或使用者建立的 Tag，使用穩定 slug 避免重複。
- `user_profile_tags` 為使用者與 Tag 的關聯表，使用複合主鍵，維持 3NF。
- `user_sessions` 保存雜湊後 Token、到期時間、最後使用時間與裝置標籤；明文 Token 只存在 HttpOnly Cookie。

Stage 5 資料表由 `0007_stage5_user_accounts.py` 建立，Google identity 與 nullable password 由 `0008_google_oauth_identity.py` 建立，管理員／Google user email 重疊規則由 `0009_allow_google_user_admin_email_overlap.py` 建立；downgrade 依相反順序移除，並保留既有 users/admin_sessions 資料。

## API 與授權

### Auth

- `GET /api/v1/auth/google/start`：建立短期 state／PKCE Cookie 並導向 Google。
- `GET /api/v1/auth/google/callback`：驗證 state、PKCE、Google verified email 與 subject，建立或取得一般使用者與 BiteMap Session。
- `POST /api/v1/auth/session/refresh`：驗證目前 Session 並延長有效期。
- `DELETE /api/v1/auth/session`：撤銷目前 Session 並清除 Cookie。
- `GET /api/v1/auth/me`：回傳目前登入者基本身分。

### Profile

- `GET /api/v1/me/profile`：只有登入者本人可讀取自己的完整 profile。
- `PATCH /api/v1/me/profile`：只有本人可修改名稱、簡介、頭像 URL 與 Tag。
- `GET /api/v1/profiles/{user_id}`：公開資料只回傳頭像、名稱、簡介與 Tag，不回傳 email、Session 或其他私人資料。
- `GET /api/v1/me/sessions`：列出本人裝置 Session，Token 不回傳。
- `DELETE /api/v1/me/sessions/{session_id}`：撤銷指定裝置 Session；只能撤銷自己的 Session。

後端所有 `/api/v1/admin/*` 仍由既有 `require_admin` 驗證，不接受一般 user Session。

## 前端流程

- `/login`：只提供 Google 登入，成功後導向 `/profile`；未登入造訪 App 路由一律回到此頁。
- `/profile`：登入者自己的公開資料與 Stage 5 基本資料；未登入導向 `/login`。
- `/profile/settings`：自己的設定表單與裝置 Session 管理；不讓公開 profile 直接變成編輯表單。
- `/profiles/[userId]`：公開 profile 只讀頁，供未來社交入口使用。
- 登出由 profile／settings 共用，撤銷目前 Session 後導向 `/login`。

前端不保存 Token、不把登入狀態放在 localStorage，也不依賴隱藏按鈕提供權限；所有權限結果以 API 回應為準。

## 錯誤與安全

- Google callback 僅接受 state 相符且 PKCE 驗證完成的授權碼，並要求 `email_verified=true`。
- 管理員 email 與 Google user email 可以相同，但不共用 users row；Google `sub` 對應獨立的 `role=user`，避免影響 `/admin/login`。
- Session Token 使用 `secrets.token_urlsafe`，資料庫只保存 SHA-256 digest。
- Cookie 在 development/test 可使用非 Secure，其他環境強制 Secure；始終 HttpOnly、SameSite=Lax、Path=/。
- 過期或撤銷 Session 一律回 401；refresh 不會復活已撤銷的 Session。

## 測試與完成條件

- 後端整合測試涵蓋 Google start／callback、重複 subject、email 衝突、me、refresh、logout、profile 私有／公開欄位與跨使用者 Session 權限。
- 角色測試確認 user 無法存取 admin API。
- 前端測試涵蓋未登入導向登入頁、只提供 Google 登入的入口；Playwright 覆蓋登入入口與個人頁主要流程。
- 完成後執行 formatter、lint、typecheck、backend/frontend tests、build，以及 OpenAPI TypeScript client 產生與編譯。
