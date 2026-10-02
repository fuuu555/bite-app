# Stage 8 social completion design

## Scope

This finishing pass makes the social hub clearer without changing meal creation, meal membership, or meal-chat permissions. It covers the renamed footer entry, the direct-chat state after an unfriend action, the selected block entry point, and a recoverable admin-shell failure state.

## Interaction design

- The footer label for `/chat` becomes `好友/聊天`; the route remains unchanged.
- Removing a friendship keeps the canonical direct-conversation history. Both affected online users receive a targeted `social.updated` WebSocket event and the chat hub shows a concise notice: the friendship ended, history remains, and later private messaging follows the recipient's setting.
- Blocking uses option A: a `更多操作` control on a public profile opens a small action menu. Choosing `封鎖` opens the shared in-app confirmation dialog. The dialog explains that friendship, direct messaging, and following stop while existing history remains. Unblock remains an explicit direct action only for the blocker.
- The admin shell keeps redirecting unauthenticated users to login. Any other `/me` failure becomes an accessible error panel with `重試` and `前往管理員登入`, rather than a permanent loading skeleton. Existing restaurant, cuisine, and avatar-management routes remain unchanged.

## Data and realtime behavior

`social.updated` gains optional `action` and `conversation_id` fields. The unfriend endpoint sends `action: friend_removed` and the existing direct conversation ID to both participants. The WebSocket payload is only a UI invalidation and notice signal; REST remains authoritative for relationship and conversation data. No REST schema, migration, meal-domain rule, or direct-message permission rule changes.

## Validation

Run frontend formatting, lint, type checks, tests, and production build; run backend formatting, Ruff, Pyright, and tests. Include the new behavior in the Stage 8 requirements and development-plan status. The final Git history is intentionally squashed to one Stage 8 commit on top of `bd2a954937cd92543a5071810942f8c0f280514d`.
