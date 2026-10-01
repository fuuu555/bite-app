# Profile tabs and local avatar assets

## Goal

Make the authenticated profile useful instead of presenting disabled labels, remove the duplicate empty-state meal CTA, and add an extensible local avatar asset flow before S3 storage is introduced.

## User experience

- The profile page has three real tabs: 公開資料, 美食留言, 收藏.
- The public tab keeps profile identity, tags, and the existing food-map placeholder.
- The reviews tab lists the current user's valid review entries and links each item to its restaurant.
- The favorites tab lists the existing favorite API results and has a clear empty state.
- The meals empty state keeps only the page-header create action.
- Admins manage avatar assets from a dedicated admin navigation item. They can upload an image, rename it, activate it, or deactivate it; deactivation is soft and does not break profiles already using the asset.
- Users choose an active built-in avatar from profile settings. Google and existing HTTPS avatar URLs remain compatible.

## Storage and data model

Avatar binaries are stored in the local backend media directory under `media/avatars/`; PostgreSQL stores only metadata and the generated storage key. The profile references an avatar asset by UUID and keeps the existing URL field for Google/external compatibility. A storage service boundary keeps the file API replaceable by S3 later.

Only JPEG, PNG, and WebP image signatures are accepted. The server enforces a size limit, generates a UUID filename, and never uses the client filename as a path. Active assets are selectable by users; inactive assets remain readable for profiles that already reference them.

## API boundaries

- `GET /api/v1/avatar-assets`: list active selectable assets for authenticated users.
- `GET /api/v1/me/reviews`: list the current user's non-deleted review entries with restaurant summary.
- `GET /api/v1/admin/avatar-assets`: list all avatar assets for admins.
- `POST /api/v1/admin/avatar-assets`: multipart upload and create an asset for admins.
- `PATCH /api/v1/admin/avatar-assets/{id}`: update display name or active state for admins.
- `PATCH /api/v1/me/profile`: accepts an optional avatar asset id and validates that it is active.

Every admin endpoint uses the existing server-side admin session guard. Profile asset selection uses the existing user session guard and never accepts an arbitrary file path or asset owned by another scope.

## Verification

- Migration upgrade and downgrade are reversible.
- Backend tests cover unauthorized admin access, upload validation, active/inactive selection, profile selection, and current-user review listing.
- Frontend tests cover profile tab switching, favorite/review loading states, duplicate CTA removal, and avatar selection feedback.
- Ruff, Pyright, frontend lint/typecheck/test/build, format check, OpenAPI generation, and the Impeccable detector run after implementation.

## Explicitly out of scope

- S3-compatible storage, signed upload URLs, CDN delivery, image transformation, and full image-content validation.
- User-uploaded avatars; only administrators upload the local avatar library in this iteration.
