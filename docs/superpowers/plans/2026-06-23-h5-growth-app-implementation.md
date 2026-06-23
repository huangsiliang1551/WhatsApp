# H5 Growth App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the current H5 member experience into the approved growth-oriented task app with a four-tab structure, clearer home/task/earnings/me responsibilities, and multilingual-safe layout behavior.

**Architecture:** Keep the existing H5 route shell and service contracts, but refactor the presentation layer around a new information hierarchy. Minimize behavioral churn in `useH5MemberApp`, move page-specific view decisions into page components and shared helpers, and lock the redesign with focused Vitest coverage before changing production code.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, existing H5 shared utilities and CSS.

---

### Task 1: Lock the redesigned shell and page hierarchy with failing tests

**Files:**
- Create: `frontend/src/pages/h5-member/h5Shell.test.tsx`
- Modify: `frontend/src/pages/h5-member/h5Pages.test.tsx`
- Read for context: `frontend/src/pages/h5-member/H5PageShell.tsx`
- Read for context: `frontend/src/pages/h5-member/HomePage.tsx`
- Read for context: `frontend/src/pages/h5-member/TasksPage.tsx`

- [ ] **Step 1: Write the failing shell tests**

```tsx
it("renders tabbar as home tasks earnings me", async () => {
  const { H5PageShell } = await import("./H5PageShell");
  renderShell({ primaryTabId: "home" });

  expect(screen.getByRole("button", { name: /home/i })).toBeTruthy();
  expect(screen.getByRole("button", { name: /tasks/i })).toBeTruthy();
  expect(screen.getByRole("button", { name: /earnings/i })).toBeTruthy();
  expect(screen.getByRole("button", { name: /me/i })).toBeTruthy();
  expect(screen.queryByRole("button", { name: /messages/i })).toBeNull();
});
```

- [ ] **Step 2: Run the new shell test and confirm RED**

Run: `npm test -- h5Shell.test.tsx`
Expected: FAIL because the existing shell still renders `Messages` and does not render `Earnings`.

- [ ] **Step 3: Extend `h5Pages.test.tsx` with failing home/tasks hierarchy tests**

```tsx
it("HomePage renders earnings hero before task sections and keeps primary CTA reachable", async () => {
  const { HomePage } = await import("./HomePage");
  render(<HomePage {...homeProps} />);

  const hero = screen.getByText(/today/i);
  const taskSection = screen.getByText(/current main task|current main action/i);
  expect(hero.compareDocumentPosition(taskSection)).toBeTruthy();
  expect(screen.getByRole("button", { name: /continue|claim|recharge|withdraw/i })).toBeTruthy();
});

it("TasksPage renders grouped sections in stable order", async () => {
  const { TasksPage } = await import("./TasksPage");
  render(<TasksPage {...tasksPropsWithMixedStatuses} />);

  const labels = screen.getAllByRole("heading").map((node) => node.textContent ?? "");
  expect(labels).toEqual([
    expect.stringMatching(/in progress/i),
    expect.stringMatching(/available|pending/i),
    expect.stringMatching(/completed/i),
    expect.stringMatching(/expired/i),
  ]);
});
```

- [ ] **Step 4: Run the focused page tests and confirm RED**

Run: `npm test -- h5Pages.test.tsx`
Expected: FAIL because the current home structure and task grouping labels do not match the new design.

- [ ] **Step 5: Commit the failing tests checkpoint**

```bash
git add frontend/src/pages/h5-member/h5Shell.test.tsx frontend/src/pages/h5-member/h5Pages.test.tsx
git commit -m "test: lock h5 growth app shell and page hierarchy"
```

### Task 2: Refactor shared helpers and shell for multilingual-safe four-tab navigation

**Files:**
- Modify: `frontend/src/pages/h5-member/H5PageShell.tsx`
- Modify: `frontend/src/pages/h5-member/shared.tsx`
- Modify: `frontend/src/pages/h5-member/i18n/en.ts`
- Modify: `frontend/src/pages/h5-member/i18n/zh-CN.ts`
- Modify: `frontend/src/styles/h5-member.css`
- Test: `frontend/src/pages/h5-member/h5Shell.test.tsx`

- [ ] **Step 1: Implement minimal shared-helper changes**

```ts
export type ProfileQuickAction = {
  key: "promotion" | "orders" | "tickets" | "contact";
  label: string;
  description: string;
  path: string;
  icon: JSX.Element;
};

function getCurrentLocale(): string {
  if (typeof document !== "undefined" && document.documentElement.lang) return document.documentElement.lang;
  if (typeof navigator !== "undefined" && navigator.language) return navigator.language;
  return "en-US";
}
```

- [ ] **Step 2: Replace label-derived profile icons and locale-hardcoded formatting**

```ts
export function formatTimestamp(value: string | null): string {
  if (!value) return t("common.none");
  return new Date(value).toLocaleString(getCurrentLocale());
}

export function formatMoney(value: number, currency = "USD"): string {
  return new Intl.NumberFormat(getCurrentLocale(), {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}
```

- [ ] **Step 3: Update the shell tab model and route grouping**

```tsx
[
  { id: "home", label: t("shell.tabHome"), path: buildH5Path("/h5/home", route.siteKey), icon: <HomeOutlined /> },
  { id: "tasks", label: t("shell.tabTasks"), path: buildH5Path("/h5/tasks", route.siteKey), icon: <AppstoreOutlined /> },
  { id: "earnings", label: t("shell.tabEarnings"), path: buildH5Path("/h5/wallet", route.siteKey), icon: <WalletOutlined /> },
  { id: "profile", label: t("shell.tabProfile"), path: buildH5Path("/h5/me", route.siteKey), icon: <UserOutlined /> },
]
```

- [ ] **Step 4: Add CSS safeguards for variable-width labels**

```css
.h5-member-tabbar-item {
  min-inline-size: 0;
}

.h5-member-tabbar-item span:last-child,
.h5-member-topbar-title-group span,
.h5-member-topbar-title-group strong {
  overflow-wrap: anywhere;
  white-space: normal;
  text-wrap: balance;
}
```

- [ ] **Step 5: Run the shell test and confirm GREEN**

Run: `npm test -- h5Shell.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit the shell/navigation refactor**

```bash
git add frontend/src/pages/h5-member/H5PageShell.tsx frontend/src/pages/h5-member/shared.tsx frontend/src/pages/h5-member/i18n/en.ts frontend/src/pages/h5-member/i18n/zh-CN.ts frontend/src/styles/h5-member.css frontend/src/pages/h5-member/h5Shell.test.tsx
git commit -m "feat: refactor h5 shell for growth app navigation"
```

### Task 3: Rebuild Home and Tasks around the approved primary journey

**Files:**
- Modify: `frontend/src/pages/h5-member/HomePage.tsx`
- Modify: `frontend/src/pages/h5-member/TasksPage.tsx`
- Modify: `frontend/src/pages/h5-member/shared.tsx`
- Modify: `frontend/src/styles/h5-member.css`
- Test: `frontend/src/pages/h5-member/h5Pages.test.tsx`

- [ ] **Step 1: Implement the home-page section reorder with one dominant task CTA**

```tsx
<section className="h5-card h5-member-home-growth-hero">
  <SectionHeader meta={t("home.todayTargetMeta")} title={t("home.todayEarningsTitle")} />
  <div className="h5-member-home-growth-metrics">...</div>
  <div className="h5-member-home-task-callout">...</div>
</section>
```

- [ ] **Step 2: Replace the old quick-grid-first structure with secondary sections**

```tsx
<section className="h5-card">
  <SectionHeader title={t("home.inProgressSection")} />
  ...
</section>
<section className="h5-card">
  <SectionHeader title={t("home.recommendedTasksSection")} />
  ...
</section>
```

- [ ] **Step 3: Rebuild TasksPage grouping and summary copy**

```tsx
const available = taskInstances.filter((task) => task.status === "pending_claim");
renderPartition(t("tasks.groupInProgress"), inProgress);
renderPartition(t("tasks.groupAvailable"), available);
renderPartition(t("tasks.groupCompleted"), completed);
renderPartition(t("tasks.groupExpired"), expired);
```

- [ ] **Step 4: Add multilingual-safe card layout rules**

```css
.h5-member-home-growth-metrics,
.h5-task-instance-card,
.h5-member-list-row-copy,
.h5-member-profile-quick-copy {
  min-inline-size: 0;
}

.h5-member-home-growth-metrics strong,
.h5-task-instance-card strong,
.h5-member-list-row-title strong {
  overflow-wrap: anywhere;
}
```

- [ ] **Step 5: Run the page tests and confirm GREEN**

Run: `npm test -- h5Pages.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit the home/tasks redesign**

```bash
git add frontend/src/pages/h5-member/HomePage.tsx frontend/src/pages/h5-member/TasksPage.tsx frontend/src/pages/h5-member/shared.tsx frontend/src/styles/h5-member.css frontend/src/pages/h5-member/h5Pages.test.tsx
git commit -m "feat: redesign h5 home and tasks for growth app flow"
```

### Task 4: Consolidate Earnings and Me into stable value/service centers

**Files:**
- Modify: `frontend/src/pages/h5-member/ProfilePage.tsx`
- Modify: `frontend/src/pages/h5-member/RechargePage.tsx`
- Modify: `frontend/src/pages/h5-member/WithdrawPage.tsx`
- Modify: `frontend/src/pages/h5-member/useH5MemberApp.ts`
- Modify: `frontend/src/pages/H5App.tsx`
- Modify: `frontend/src/styles/h5-member.css`
- Test: `frontend/src/pages/h5-member/h5Pages.test.tsx`

- [ ] **Step 1: Route the tab selection model to treat wallet/recharge/withdraw as the earnings branch**

```ts
if (route.page === "recharge" || route.page === "withdraw") return "earnings";
```

- [ ] **Step 2: Reframe RechargePage as the earnings landing page**

```tsx
<SectionHeader meta={t("earnings.availableBalance", { amount: ... })} title={t("earnings.title")} />
<section className="h5-member-earnings-summary-grid">...</section>
<section className="h5-member-earnings-actions">...</section>
```

- [ ] **Step 3: Refactor ProfilePage into account-and-service presentation**

```tsx
<SectionHeader meta={t("profile.accountCenter")} title={t("profile.title")} />
<div className="h5-member-profile-service-groups">...</div>
```

- [ ] **Step 4: Run the focused H5 page suite**

Run: `npm test -- h5Pages.test.tsx h5Shell.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit the earnings/me refactor**

```bash
git add frontend/src/pages/h5-member/ProfilePage.tsx frontend/src/pages/h5-member/RechargePage.tsx frontend/src/pages/h5-member/WithdrawPage.tsx frontend/src/pages/h5-member/useH5MemberApp.ts frontend/src/pages/H5App.tsx frontend/src/styles/h5-member.css frontend/src/pages/h5-member/h5Pages.test.tsx frontend/src/pages/h5-member/h5Shell.test.tsx
git commit -m "feat: reshape h5 earnings and me pages"
```

### Task 5: Verify the redesign end-to-end in the existing frontend test lane

**Files:**
- Test: `frontend/src/pages/h5-member/h5Shell.test.tsx`
- Test: `frontend/src/pages/h5-member/h5Pages.test.tsx`
- Test: `frontend/src/pages/h5-member/h5Auth.test.tsx`

- [ ] **Step 1: Add the auth-guard regression for the new earnings route**

```tsx
it("preserves redirect path for earnings route", async () => {
  const { useAuthGuard } = await import("./useAuthGuard");
  ...
  expect(onNavigate).toHaveBeenCalledWith("/h5/login?redirect=%2Fh5%2Fwallet");
});
```

- [ ] **Step 2: Run the targeted frontend verification suite**

Run: `npm test -- h5Shell.test.tsx h5Pages.test.tsx h5Auth.test.tsx`
Expected: PASS.

- [ ] **Step 3: Run frontend typecheck**

Run: `npm run typecheck`
Expected: no TypeScript errors.

- [ ] **Step 4: Commit the verification checkpoint**

```bash
git add frontend/src/pages/h5-member/h5Auth.test.tsx
git commit -m "test: verify h5 growth app routes and auth guard"
```

## Self-Review

- Spec coverage:
  - four-tab IA: Task 2
  - home/task/earnings/me role split: Tasks 3-4
  - multilingual width constraints: Tasks 2-4
  - primary task journey: Task 3
  - service/support demotion and regrouping: Task 4
- Placeholder scan: no TODO/TBD placeholders remain
- Type consistency:
  - use `earnings` as the new primary tab id
  - use `ProfileQuickAction` instead of label-derived icon inference
