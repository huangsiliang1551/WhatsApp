# Permission Center Backend Final State

## Scope

This document is the canonical handoff for the formal backend CRUD permission center in `E:\codex\WhatsApp`.

It supersedes older planning-only descriptions that still mention the pre-template-CRUD API surface.

## Runtime Rules

- Canonical permission codes are the only runtime truth.
- Permission-center actor parsing now reuses the shared actor builder through strict `Bearer` JWT enforcement.
- Permission-center endpoints reject header-only `X-Actor-*` identity when auth is required.
- Valid Bearer JWTs are accepted without legacy `X-Actor-*` headers on shared authenticated routes.
- When a Bearer JWT is present, legacy `X-Actor-Name` and `X-Actor-Account-Ids` no longer override JWT identity or scope.
- Agency-scoped role/template writes never accept legacy permission aliases.
- `super_admin_only` permission codes cannot be assigned to agency roles or agency templates.
- All permission-center reads sanitize stray `super_admin_only` and unknown permission codes from stored rows.
- Formal actor scope is derived from JWT/session context, not from free-form frontend role claims.
- `super_admin` semantics are canonicalized by role, not by `agency_id is None`.

## Backend Coverage

### Roles

- `GET /api/permissions/agency/{agency_id}`
  - Returns agency role summaries/configurations.
  - Excludes template rows from the role list.
  - Includes `member_count`.
  - Includes draft-like rows for member roles that exist in `agency_members` but do not yet have a permission config row.

- `PUT /api/permissions/agency/{agency_id}`
  - Upserts agency role permissions.
  - Clears `template_name` provenance on manual edits.
  - Rejects writes against template rows.
  - Requires canonical `roles.edit_perms`.
  - Creating a missing role config also requires canonical `roles.create`.
  - New rows are limited to builtin role keys or `custom_*`.

- `POST /api/permissions/custom-role`
  - Creates an agency custom role.
  - Agency members write to their own `agency_id`.
  - `super_admin` must pass explicit `agency_id`.
  - Requires canonical `roles.create`.

- `DELETE /api/permissions/agency/{agency_id}/roles/{role_name}`
  - Deletes agency custom roles only.
  - Rejects builtin roles and template rows.
  - Rejects deletion when members are still assigned.
  - Requires canonical `roles.delete`.

### Templates

- `GET /api/permissions/templates`
  - Returns preset templates plus agency custom templates.
  - Non-super-admin actors only see custom templates from their own agency.
  - Read payloads are sanitized.

- `POST /api/permissions/templates`
  - Creates an agency custom template backed by `role_permissions.is_template = true`.
  - Agency members cannot target foreign agencies.
  - `super_admin` must pass explicit `agency_id`.
  - Requires canonical `roles.create`.

- `PUT /api/permissions/templates/{template_id}`
  - Updates an agency custom template.
  - Enforces same-agency access.
  - Requires canonical `roles.edit_perms`.

- `DELETE /api/permissions/templates/{template_id}`
  - Deletes an agency custom template.
  - Enforces same-agency access.
  - Requires canonical `roles.delete`.

### Supporting Operations

- `GET /api/permissions/definitions`
  - Returns canonical permission definitions grouped by module.
  - Requires canonical `roles.view`.

- `GET /api/auth/permissions`
  - Returns canonical effective permissions and derived menus for the current actor.
  - Uses the same shared actor builder, but the permission center requires a valid Bearer JWT instead of header-only actor injection.

- `POST /api/permissions/apply-template`
  - Applies preset or allowed custom template permissions to a target role.
  - Persists `template_name` provenance on the role row.
  - Missing target agencies return `404`.
  - Agency-scoped custom templates cannot be applied across agencies, including by `super_admin`.
  - Creating a missing target role config also requires canonical `roles.create`.
  - Requires canonical `roles.edit_perms`.

- `POST /api/permissions/copy`
  - Copies non-template role configs from source agency to target agency.
  - Existing target non-template roles are replaced.
  - Requires canonical `agents.permissions`.

## Data Model Notes

Primary storage remains `role_permissions`:

- Role row:
  - `agency_id != NULL`
  - `is_template = false`
  - `role_name = builtin role or custom_*`

- Template row:
  - `agency_id != NULL`
  - `is_template = true`
  - `role_name = custom_template_*`
  - `template_name = user-facing template label`

Template provenance on roles is stored in:

- `role_permissions.template_name`

This field is:

- set by `POST /api/permissions/apply-template`
- cleared by manual `PUT /api/permissions/agency/{agency_id}`

## Frontend Contract Alignment

Current frontend role-center contract in `frontend/src/services/permissions.ts` expects:

- role summaries from `GET /api/permissions/agency/{agency_id}`
- `member_count` from the same API
- placeholder role rows with `id = null` to remain `draft/unconfigured`
- custom-role creation with explicit `agencyId`
- template listing and template application
- structured backend `detail.message` errors to surface as readable UI messages

The frontend no longer depends on `/api/agents/{agency_id}/members` for permission-center role summaries.

## Verification Status

Verified in this workspace:

- `python -m pytest tests/test_permission_center_authz.py tests/test_permission_resolution.py -q`
- `python -m pytest tests/test_permission_bridge.py tests/test_permission_canonical_only.py tests/test_permission_role_delete.py tests/test_permission_route_cleanup_remaining.py tests/test_auth.py -k "permission or media_library_permissions_are_explicit or extended_roles_are_accepted_for_authorized_reads" -q`
- `npm run typecheck`
- `npm test -- src/services/permissions.test.ts src/hooks/usePermissions.test.ts src/pages/rolesPage.test.tsx src/pages/agentPermissionPages.test.ts`

Additional boundary verification completed:

- super-admin template create requires explicit `agency_id`
- agency member cannot create template for foreign agency
- agency member cannot update/delete foreign-agency template
- `PUT /api/permissions/agency/{agency_id}` cannot create a missing role without `roles.create`
- `POST /api/permissions/apply-template` cannot create a missing role without `roles.create`
- `POST /api/permissions/apply-template` rejects missing agencies and foreign-agency custom templates
- shared authenticated routes accept JWT-only agent and super-admin actors without `X-Actor-*`
- invalid Bearer tokens do not fall back to legacy header actors
- permission-center endpoints reject header-only actor identity when `AUTH_REQUIRED=true`
- Bearer JWT identity/scope wins over legacy `X-Actor-Name` and `X-Actor-Account-Ids`
- API stats and rate-limit middleware key JWT requests by JWT-derived scope instead of legacy actor headers

## Remaining Work Outside This Scope

These are not backend CRUD-center gaps anymore:

- template management UI on the frontend
- stale planning-doc cleanup
- warning cleanup:
  - `StarletteDeprecationWarning` about `httpx2`
  - `PytestConfigWarning` about `asyncio_mode`
