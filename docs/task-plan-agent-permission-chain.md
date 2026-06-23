# Agent Permission Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the existing `/system/agents` flow so super admins manage agent agencies through one canonical chain: agency overview -> granted permission pool -> agency roles -> agency members, while removing the need for a separate top-level role-management workflow.

**Architecture:** Keep `app/api/routes/agency.py` as the canonical agency domain for super-admin workflows, keep `app/api/routes/permissions_api.py` as the canonical role-permission CRUD domain, and introduce an explicit agency-level permission-grant layer that constrains what roles can contain. On the frontend, convert agent detail into the main workspace and reuse role-center logic inside the agent detail page instead of treating `/system/roles` as the primary navigation entry.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, Vite, TypeScript, Ant Design, Vitest, Pytest

---

## File Map

### Backend

- Modify: `app/api/routes/agency.py`
  - Add agency-granted-permissions read/write endpoints.
  - Tighten member-role update validation so assigned roles must already exist in the agency.
- Modify: `app/services/agency_service.py`
  - Add query/update logic for agency permission grants.
  - Add validation helpers for member role assignment and agency role existence.
- Modify: `app/api/routes/permissions_api.py`
  - Enforce `role.permissions ⊆ agency granted permissions` for create/update/apply-template flows.
- Modify: `app/db/models.py`
  - Add an explicit `AgencyPermissionGrant` model/table.
- Create: `alembic/versions/20260622_XXXX_agency_permission_grants.py`
  - Create the new table and indexes.

### Frontend

- Modify: `frontend/src/pages/AgentsPage.tsx`
  - Remove standalone “角色中心 / 权限角色中心” primary workflow emphasis.
  - Route detail entry to the agent detail workspace.
- Modify: `frontend/src/pages/AgentDetailPage.tsx`
  - Convert into the main super-admin workspace with tabs:
    - overview
    - permission-grants
    - roles
    - members
- Modify: `frontend/src/pages/RolesPage.tsx`
  - Extract reusable agency-role management content into a shared panel component.
- Create: `frontend/src/components/agents/AgencyRolesPanel.tsx`
  - Shared role table / role edit / apply template / custom role creation UI.
- Create: `frontend/src/components/agents/AgencyPermissionGrantsPanel.tsx`
  - Super-admin-only UI for the agency granted permission pool.
- Create: `frontend/src/components/agents/AgencyMembersPanel.tsx`
  - Shared agency member CRUD UI with role select constrained to existing roles only.
- Modify: `frontend/src/services/permissions.ts`
  - Add fetch/update agency granted-permission pool methods.
  - Expose role summaries for embedded agent-detail usage.
- Modify: `frontend/src/services/api.ts`
  - Add agency granted-permission APIs.
- Modify: `frontend/src/routes/consoleRoutes.ts`
  - Demote `/system/roles` from the main people menu or hide it from super-admin day-to-day nav.

### Tests

- Create: `tests/test_agency_permission_grants_api.py`
  - Covers agency permission pool CRUD and enforcement.
- Modify: `tests/test_permission_center_authz.py`
  - Add subset enforcement checks against agency granted permissions.
- Modify: `tests/test_permission_bridge.py`
  - Verify resolved permissions remain canonical after agency-grant enforcement.
- Modify: `frontend/src/pages/agentPermissionPages.test.ts`
  - Assert agent pages no longer treat free-text custom role names as valid assignment flow.
- Modify: `frontend/src/pages/rolesPage.test.tsx`
  - Cover embedded role-center usage assumptions if extracted.
- Create: `frontend/src/components/agents/agencyPermissionPanels.test.tsx`
  - Cover tab-level interaction for grants / roles / members.

---

## Product Rules To Preserve

- Super admin manages agencies from `/system/agents`.
- Roles belong to one agency only.
- Members do not receive direct permissions.
- Members only receive roles.
- Agency roles may only contain permissions already granted to that agency by super admin.
- Agent-side role self-management remains possible later, but this plan only restructures the super-admin workflow.
- `/system/roles` may remain as a deep-link/debug entry, but not as the primary super-admin operational path.

---

### Task 1: Add Explicit Agency Permission Grants Model and API

**Files:**
- Modify: `app/db/models.py`
- Create: `alembic/versions/20260622_XXXX_agency_permission_grants.py`
- Modify: `app/services/agency_service.py`
- Modify: `app/api/routes/agency.py`
- Test: `tests/test_agency_permission_grants_api.py`

- [ ] **Step 1: Write the failing backend tests**

Create `tests/test_agency_permission_grants_api.py` with coverage for:

```python
def test_super_admin_can_get_empty_agency_permission_grants(...): ...
def test_super_admin_can_update_agency_permission_grants(...): ...
def test_unknown_permission_codes_are_rejected(...): ...
def test_non_super_admin_cannot_update_foreign_agency_permission_grants(...): ...
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
python -m pytest tests/test_agency_permission_grants_api.py -q
```

Expected:
- Failing with missing model / missing endpoint / 404 responses.

- [ ] **Step 3: Add the SQLAlchemy model**

In `app/db/models.py`, add a focused model similar to:

```python
class AgencyPermissionGrant(Base, TimestampMixin):
    __tablename__ = "agency_permission_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True, nullable=False, unique=True)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

- [ ] **Step 4: Add the Alembic migration**

Create `alembic/versions/20260622_XXXX_agency_permission_grants.py` to:
- create `agency_permission_grants`
- unique-index `agency_id`
- default `permissions` to empty JSON array where supported

- [ ] **Step 5: Implement service methods**

Add methods to `app/services/agency_service.py`:

```python
def get_permission_grants(self, agency_id: str) -> list[str]: ...
def update_permission_grants(self, agency_id: str, permissions: list[str], *, actor_id: str) -> list[str]: ...
```

Rules:
- reject unknown permission codes
- normalize canonical codes only
- store sorted unique permission list

- [ ] **Step 6: Add agency endpoints**

Extend `app/api/routes/agency.py` with:

```python
@router.get("/{agency_id}/granted-permissions")
async def get_agency_granted_permissions(...): ...

@router.put("/{agency_id}/granted-permissions")
async def update_agency_granted_permissions(...): ...
```

Permissions:
- read: `agents.permissions` or `roles.view`
- write: `agents.permissions`

- [ ] **Step 7: Run backend tests**

Run:

```bash
python -m pytest tests/test_agency_permission_grants_api.py -q
```

Expected:
- PASS

- [ ] **Step 8: Commit**

```bash
git add app/db/models.py alembic/versions/20260622_XXXX_agency_permission_grants.py app/services/agency_service.py app/api/routes/agency.py tests/test_agency_permission_grants_api.py
git commit -m "feat: add agency permission grants"
```

---

### Task 2: Enforce Agency Grant Subset in Role CRUD

**Files:**
- Modify: `app/api/routes/permissions_api.py`
- Modify: `tests/test_permission_center_authz.py`
- Modify: `tests/test_permission_bridge.py`

- [ ] **Step 1: Write the failing authz tests**

Add tests to `tests/test_permission_center_authz.py` for:

```python
def test_create_custom_role_rejects_permissions_outside_agency_grants(...): ...
def test_update_agency_role_rejects_permissions_outside_agency_grants(...): ...
def test_apply_template_rejects_permissions_outside_agency_grants(...): ...
```

Each test should:
- create agency
- set agency grants to a small subset
- attempt role write with one out-of-scope permission
- expect `403` or `400` with a clear error message

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
python -m pytest tests/test_permission_center_authz.py -k "outside_agency_grants" -q
```

Expected:
- FAIL because no subset enforcement exists yet.

- [ ] **Step 3: Implement subset enforcement**

In `app/api/routes/permissions_api.py`, add a helper like:

```python
def _ensure_permissions_within_agency_grants(
    session: Session,
    agency_id: str,
    permissions: list[str],
) -> None: ...
```

Use it from:
- `PUT /api/permissions/agency/{agency_id}`
- `POST /api/permissions/custom-role`
- `POST /api/permissions/apply-template`
- `POST /api/permissions/templates` if agency templates should also be constrained

- [ ] **Step 4: Preserve super-admin-only filtering semantics**

Do not weaken existing rules:
- canonical code normalization still applies
- `super_admin_only` permissions remain forbidden for agency roles/templates
- granted permissions themselves should also reject `super_admin_only` if you do not want agencies to even hold them

- [ ] **Step 5: Add regression bridge check**

Extend `tests/test_permission_bridge.py` so DB-resolved effective permissions remain canonical and unchanged for allowed roles after the new subset gate.

- [ ] **Step 6: Run the permission regression suite**

Run:

```bash
python -m pytest tests/test_permission_center_authz.py tests/test_permission_bridge.py tests/test_permission_resolution.py -q
```

Expected:
- PASS

- [ ] **Step 7: Commit**

```bash
git add app/api/routes/permissions_api.py tests/test_permission_center_authz.py tests/test_permission_bridge.py
git commit -m "feat: enforce agency grant subset for role permissions"
```

---

### Task 3: Refactor Agent Detail Into the Primary Super-Admin Workspace

**Files:**
- Modify: `frontend/src/pages/AgentDetailPage.tsx`
- Create: `frontend/src/components/agents/AgencyRolesPanel.tsx`
- Create: `frontend/src/components/agents/AgencyMembersPanel.tsx`
- Create: `frontend/src/components/agents/AgencyPermissionGrantsPanel.tsx`
- Modify: `frontend/src/services/permissions.ts`
- Modify: `frontend/src/services/api.ts`
- Test: `frontend/src/components/agents/agencyPermissionPanels.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

Create `frontend/src/components/agents/agencyPermissionPanels.test.tsx` with tests like:

```tsx
it("renders overview, permission grants, roles, and members tabs")
it("loads role panel inside agent detail without requiring manual agency id input")
it("loads agency granted permissions for the current agent")
```

- [ ] **Step 2: Run the focused frontend test file**

Run:

```bash
npm test -- src/components/agents/agencyPermissionPanels.test.tsx
```

Expected:
- FAIL because the panels do not exist yet.

- [ ] **Step 3: Extract reusable role panel**

Move the core UI logic from `frontend/src/pages/RolesPage.tsx` into `frontend/src/components/agents/AgencyRolesPanel.tsx` with props such as:

```ts
type AgencyRolesPanelProps = {
  agencyId: string
  embedded?: boolean
  onRoleChanged?: () => Promise<void> | void
}
```

The extracted panel must:
- not require manual `Agency ID` input when `agencyId` prop is present
- preserve template apply / custom role create / delete role flows

- [ ] **Step 4: Build the granted-permissions panel**

Add `AgencyPermissionGrantsPanel.tsx` with:
- permission-module grouped checkboxes
- read current grants from backend
- save updated grant pool
- super-admin-only editing state

- [ ] **Step 5: Extract the members panel**

Move member list / add member / edit member role / remove member from `AgentDetailPage.tsx` into `AgencyMembersPanel.tsx`.

Props:

```ts
type AgencyMembersPanelProps = {
  agencyId: string
  roleOptions: Array<{ label: string; value: string }>
}
```

- [ ] **Step 6: Rebuild agent detail with tabs**

In `frontend/src/pages/AgentDetailPage.tsx`, add tabs:
- `overview`
- `permission-grants`
- `roles`
- `members`

Recommended query contract:

```ts
?tab=overview
?tab=permission-grants
?tab=roles
?tab=members
```

- [ ] **Step 7: Add client methods**

Extend:
- `frontend/src/services/api.ts`
- `frontend/src/services/permissions.ts`

with:

```ts
getAgencyGrantedPermissions(agencyId: string)
updateAgencyGrantedPermissions(agencyId: string, permissions: string[])
```

- [ ] **Step 8: Run focused frontend tests**

Run:

```bash
npm test -- src/components/agents/agencyPermissionPanels.test.tsx src/pages/rolesPage.test.tsx
```

Expected:
- PASS

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/AgentDetailPage.tsx frontend/src/components/agents/AgencyRolesPanel.tsx frontend/src/components/agents/AgencyMembersPanel.tsx frontend/src/components/agents/AgencyPermissionGrantsPanel.tsx frontend/src/services/permissions.ts frontend/src/services/api.ts frontend/src/components/agents/agencyPermissionPanels.test.tsx
git commit -m "feat: make agent detail the permission management workspace"
```

---

### Task 4: Remove Free-Text Role Assignment From Member Editing

**Files:**
- Modify: `frontend/src/pages/AgentsPage.tsx`
- Modify: `frontend/src/pages/AgentDetailPage.tsx`
- Modify: `frontend/src/components/agents/AgencyMembersPanel.tsx`
- Modify: `app/api/routes/agency.py`
- Modify: `app/services/agency_service.py`
- Test: `frontend/src/pages/agentPermissionPages.test.ts`

- [ ] **Step 1: Write the failing tests**

Update `frontend/src/pages/agentPermissionPages.test.ts` to assert:

```ts
expect(agentDetailPageSource).not.toContain("customRoleName")
expect(agentsPageSource).not.toContain("customRoleName")
```

Add backend tests if needed to reject unknown/nonexistent role assignment:

```python
def test_member_role_update_rejects_nonexistent_agency_role(...): ...
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
npm test -- src/pages/agentPermissionPages.test.ts
python -m pytest tests/test_agency_permission_grants_api.py -k "nonexistent_agency_role" -q
```

Expected:
- FAIL

- [ ] **Step 3: Change member UI to existing-role selection only**

In agent member forms:
- replace mixed preset/custom role mode
- only show role options from current agency roles
- add a `Create role` action instead of free-text input

- [ ] **Step 4: Reject invalid role assignment server-side**

In `app/services/agency_service.py`, add validation:

```python
def ensure_agency_role_exists(self, agency_id: str, role: str) -> None: ...
```

Call it from:
- `add_member`
- `update_member_role`

- [ ] **Step 5: Run tests**

Run:

```bash
npm test -- src/pages/agentPermissionPages.test.ts
python -m pytest tests/test_agency_permission_grants_api.py tests/test_permission_center_authz.py -q
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/AgentsPage.tsx frontend/src/pages/AgentDetailPage.tsx frontend/src/components/agents/AgencyMembersPanel.tsx app/api/routes/agency.py app/services/agency_service.py frontend/src/pages/agentPermissionPages.test.ts
git commit -m "refactor: constrain agency members to existing roles"
```

---

### Task 5: Demote `/system/roles` From Primary Navigation

**Files:**
- Modify: `frontend/src/routes/consoleRoutes.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/RolesPage.tsx`
- Test: `frontend/src/hooks/usePermissions.test.ts`

- [ ] **Step 1: Write the failing navigation tests**

Add a frontend navigation test ensuring:
- agent detail provides the primary path into agency roles
- `/system/roles` remains loadable by direct URL
- the main left menu no longer promotes `roles` for super-admin day-to-day use

- [ ] **Step 2: Run the failing tests**

Run:

```bash
npm test -- src/hooks/usePermissions.test.ts src/pages/rolesPage.test.tsx
```

Expected:
- FAIL or expose current menu assumptions.

- [ ] **Step 3: Update route metadata**

In `frontend/src/routes/consoleRoutes.ts`:
- set `roles.visibleInNav = false` or `hideInMenu = true`
- keep route resolution for direct links

- [ ] **Step 4: Keep deep-link compatibility**

Do not delete `/system/roles`.
Keep `RolesPage` functional for:
- internal troubleshooting
- direct links from audits
- future agent self-service reuse if needed

- [ ] **Step 5: Run frontend route checks**

Run:

```bash
npm test -- src/pages/rolesPage.test.tsx src/hooks/usePermissions.test.ts
npm run typecheck
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/consoleRoutes.ts frontend/src/App.tsx frontend/src/pages/RolesPage.tsx frontend/src/hooks/usePermissions.test.ts
git commit -m "refactor: demote standalone roles page from primary nav"
```

---

### Task 6: End-to-End Verification and Documentation

**Files:**
- Modify: `docs/permission-center-backend-final.md`
- Modify: `docs/admin-frontend-session-handoff-2026-06-12.md` or create a new focused handoff if preferred

- [ ] **Step 1: Run backend verification**

Run:

```bash
python -m pytest tests/test_agency_permission_grants_api.py tests/test_permission_center_authz.py tests/test_permission_bridge.py tests/test_permission_role_delete.py tests/test_permission_resolution.py tests/test_permission_canonical_only.py tests/test_auth.py -q
```

Expected:
- PASS

- [ ] **Step 2: Run frontend verification**

Run:

```bash
npm test -- src/components/agents/agencyPermissionPanels.test.tsx src/pages/agentPermissionPages.test.ts src/pages/rolesPage.test.tsx src/hooks/usePermissions.test.ts
npm run typecheck
```

Expected:
- PASS

- [ ] **Step 3: Update docs**

Document:
- super-admin workflow now starts from `/system/agents`
- roles belong to agencies
- agency granted-permission pool constrains all role writes
- member editing only assigns existing roles

- [ ] **Step 4: Commit**

```bash
git add docs/permission-center-backend-final.md docs/admin-frontend-session-handoff-2026-06-12.md
git commit -m "docs: document agency-first permission workflow"
```

---

## Spec Coverage Review

- Agency remains the top-level super-admin management object: covered by Tasks 3 and 5.
- Roles belong to agencies, not to a global daily workflow: covered by Tasks 3 and 5.
- Super admin can still inspect agency role state: covered by Tasks 3 and 5.
- Super admin grants a permission pool to the agency: covered by Tasks 1 and 3.
- Agency roles can only use the granted subset: covered by Task 2.
- Members only inherit via roles: covered by Task 4.

No known spec gaps remain for this restructure.

## Placeholder Scan

- No `TODO`, `TBD`, or “similar to previous task” placeholders remain.
- Each task lists concrete file paths and verification commands.
- The only migration placeholder left is the timestamp suffix in the Alembic filename, which must be replaced with the generated revision id during implementation.

## Type Consistency Review

- `agencyId` is used consistently in frontend service/input naming.
- Backend keeps `agency_id` request/response naming.
- The grant layer is consistently named `granted permissions` rather than mixing `allowlist`, `caps`, and `limits`.

---

Plan complete and saved to `docs/task-plan-agent-permission-chain.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
