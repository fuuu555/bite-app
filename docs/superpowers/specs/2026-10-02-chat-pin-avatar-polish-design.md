# Chat pin reliability and participant-action polish

## Scope

This change fixes the chat pin acknowledgement failure and completes the existing participant
avatar interaction consistently in direct chat, meal chat, and meal-member lists. It does not
change meal membership, voting, or direct-message authorization rules.

## Behaviour

### Reliable pin and unpin events

- A successful pin or unpin persists first and must acknowledge the initiating socket even when a
  different stale socket cannot receive the broadcast.
- A failed socket is removed from the realtime hub; it cannot cause the completed database action
  to be reported as `event could not be processed`.
- The WebSocket payload for `message.pinned` has `is_pinned: true` and a timestamp. The payload
  for `message.unpinned` has `is_pinned: false` and `pinned_at: null`.

### Participant avatar menu

- Every non-self participant avatar in chat messages and every meal-member avatar opens the same
  menu: `查看個人資料` plus one conversation action.
- When the relationship is `friends`, that action reads `聊天`; it opens the canonical existing
  conversation or creates it through the existing authorized endpoint.
- For all non-friend relationships, the action reads `私聊` when allowed. When the other user has
  disabled stranger messages, it remains disabled and displays the reason.
- The menu remains outside scroll clipping and supports outside-click and Escape dismissal.

### Meal host identification

- Meal cards and meal detail show the existing host name with a compact `發起人` badge.
- The host avatar receives a small distinct outline. This is presentation only and grants no new
  authority.

### Reply contrast

- A reply preview inside a left-side (other participant) message uses a readable tinted surface,
  dark primary text, and muted secondary text. It must not become white-on-white.
- The existing high-contrast own-message treatment stays unchanged.

## Technical design

- `RealtimeHub` treats `WebSocketDisconnect` as a stale recipient in every fan-out path. Delivery
  faults are isolated from the action that has already committed to PostgreSQL.
- Existing pin relationship synchronization and forced ORM reload remain the source for the
  broadcast payload.
- `ParticipantAvatarMenu` derives its action label from the already fetched relationship response;
  it does not duplicate friendship or direct-message policy in the client.
- CSS owns host and reply visual variation; no API schema or database migration is required.

## Verification

- Add realtime-hub coverage that a disconnected recipient is removed while a pin event continues
  to be dispatched to healthy recipients.
- Extend participant-menu and meal rendering coverage where practical, then run formatter, lint,
  typecheck, frontend tests, backend tests, and production build.
