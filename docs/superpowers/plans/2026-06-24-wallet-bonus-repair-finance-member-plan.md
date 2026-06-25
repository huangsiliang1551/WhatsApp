# Wallet Bonus Repair Finance Member Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the bonus-to-system-balance accounting model end to end so bonus, repair recharge, withdrawal split, reports, and member display all follow the new product rules.

**Architecture:** Introduce a unified wallet ledger service as the only write path for wallet balance changes, then migrate recharge, bonus, repair, transfer, purchase, and withdrawal flows onto it. Extend the data model to track cash/bonus/frozen split and expose that split consistently through admin finance APIs, reports, and H5 display categories while preserving a single customer-facing system balance.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, Vite, TypeScript, pytest, Vitest

---

## File Map

- Modify: `app/db/models.py`
  - Extend wallet, ledger, and withdrawal models with cash/bonus split fields and metadata needed for reports, risk, and auditing.
- Create: `app/services/wallet_ledger_service.py`
  - Centralized wallet mutation service for credit, debit, freeze, unfreeze, reversal, and split calculation.
- Create: `app/services/bonus_grant_service.py`
  - Bonus approval and ledger integration.
- Create: `app/services/recharge_repair_service.py`
  - Repair order approval and real-money ledger integration.
- Modify: `app/services/h5_member_commerce_service.py`
  - Replace direct wallet balance mutations with `WalletLedgerService`.
- Modify: `app/services/platform_withdrawal_service.py`
  - Freeze split at request time and restore exact split on rejection.
- Modify: `app/services/finance_report_service.py`
  - Replace current summary logic with cash/bonus-aware reporting and filters.
- Modify: `app/api/routes/finance.py`
  - Expose bonus/repair/report endpoints and real data instead of shallow record creation.
- Modify: `app/api/routes/payment_callback.py`
  - Route successful callbacks through the unified wallet ledger flow with idempotency.
- Modify: `app/api/routes/platform_withdrawals.py`
  - Return split and duplicate-account risk fields.
- Modify: `app/services/invite_service.py`
  - Clarify reward flow into bonus or task buckets per final rule.
- Create: `app/schemas/finance_bonus.py`
- Create: `app/schemas/recharge_repair.py`
- Create: `app/schemas/wallet_ledger.py`
- Modify: `app/schemas/platform_withdrawals.py`
- Modify: `app/schemas/h5_member_commerce.py`
- Create: `scripts/check_wallet_balance_invariants.py`
- Create: `scripts/backfill_wallet_cash_bonus.py`
- Create: `alembic/versions/<timestamp>_wallet_cash_bonus_repair_finance.py`
- Create tests:
  - `tests/services/test_wallet_ledger_service.py`
  - `tests/services/test_bonus_grant_service.py`
  - `tests/services/test_recharge_repair_service.py`
  - `tests/services/test_finance_report_service.py`
  - `tests/services/test_platform_withdrawal_service.py`
  - `tests/api/test_finance_bonus_grants.py`
  - `tests/api/test_finance_recharge_repairs.py`
  - `tests/api/test_finance_reports.py`
  - `tests/api/test_platform_withdrawals.py`
- Later frontend files:
  - `frontend/src/components/member/MemberIdLink.tsx`
  - `frontend/src/components/member/MemberProfilePopover.tsx`
  - `frontend/src/services/financeApi.ts`
  - `frontend/src/services/memberApi.ts`
  - `frontend/src/types/finance.ts`
  - `frontend/src/types/withdrawal.ts`
  - `frontend/src/types/member.ts`
  - `frontend/src/pages/FinancePage.tsx`
  - `frontend/src/pages/ReportsPage.tsx`
  - new finance subpages under `frontend/src/pages/finance/`

## Task 1: Add Failing Backend Tests For Split Wallet Accounting

**Files:**
- Create: `tests/services/test_wallet_ledger_service.py`
- Create: `tests/services/test_platform_withdrawal_service.py`
- Create: `tests/services/test_finance_report_service.py`

- [ ] **Step 1: Write the failing wallet split tests**

```python
def test_wallet_credit_bonus_updates_bonus_and_system_balances():
    ...

def test_wallet_credit_cash_updates_cash_and_system_balances():
    ...

def test_wallet_withdraw_split_prefers_cash_then_bonus():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/services/test_wallet_ledger_service.py -q`
Expected: FAIL because split fields and service do not exist yet

- [ ] **Step 3: Write minimal model and service implementation**

```python
class WalletLedgerService:
    def credit_system_cash(...): ...
    def credit_system_bonus(...): ...
    def create_withdrawal_split(...): ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/services/test_wallet_ledger_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db/models.py app/services/wallet_ledger_service.py tests/services/test_wallet_ledger_service.py
git commit -m "feat: add split wallet ledger accounting"
```

## Task 2: Add Schema And Migration Support For Cash/Bonus Split

**Files:**
- Modify: `app/db/models.py`
- Create: `alembic/versions/<timestamp>_wallet_cash_bonus_repair_finance.py`
- Create: `scripts/check_wallet_balance_invariants.py`

- [ ] **Step 1: Write the failing migration/model tests**

```python
def test_wallet_account_has_cash_bonus_split_fields():
    ...

def test_withdrawal_request_has_cash_bonus_split_fields():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/services/test_wallet_ledger_service.py -q`
Expected: FAIL on missing model fields

- [ ] **Step 3: Implement model fields and migration**

```python
system_cash_balance = mapped_column(...)
system_bonus_balance = mapped_column(...)
cash_amount = mapped_column(...)
bonus_amount = mapped_column(...)
```

- [ ] **Step 4: Run tests and migration verification**

Run: `python -m pytest tests/services/test_wallet_ledger_service.py -q`
Expected: PASS

Run: `alembic upgrade head`
Expected: migration applies cleanly

- [ ] **Step 5: Commit**

```bash
git add app/db/models.py alembic/versions scripts/check_wallet_balance_invariants.py
git commit -m "feat: add wallet split schema and invariants"
```

## Task 3: Move H5 Recharge, Transfer, Purchase, And Withdrawal To Unified Ledger Writes

**Files:**
- Modify: `app/services/h5_member_commerce_service.py`
- Test: `tests/services/test_wallet_ledger_service.py`

- [ ] **Step 1: Write failing H5 commerce integration tests**

```python
def test_h5_recharge_creates_cash_ledger_and_updates_split_wallet():
    ...

def test_task_to_system_transfer_creates_bonus_ledger_entries():
    ...

def test_h5_withdrawal_creates_cash_bonus_split_request():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/services/test_wallet_ledger_service.py -q`
Expected: FAIL because H5 service still mutates `system_balance` directly

- [ ] **Step 3: Replace direct mutations with wallet ledger service calls**

```python
wallet_service.credit_system_cash(...)
wallet_service.transfer_task_to_bonus_system(...)
wallet_service.request_withdrawal(...)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/services/test_wallet_ledger_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/h5_member_commerce_service.py tests/services/test_wallet_ledger_service.py
git commit -m "refactor: route h5 wallet flows through wallet ledger service"
```

## Task 4: Implement Bonus Grants And Recharge Repairs

**Files:**
- Create: `app/services/bonus_grant_service.py`
- Create: `app/services/recharge_repair_service.py`
- Create: `app/schemas/finance_bonus.py`
- Create: `app/schemas/recharge_repair.py`
- Modify: `app/api/routes/finance.py`
- Create tests:
  - `tests/services/test_bonus_grant_service.py`
  - `tests/services/test_recharge_repair_service.py`
  - `tests/api/test_finance_bonus_grants.py`
  - `tests/api/test_finance_recharge_repairs.py`

- [ ] **Step 1: Write failing service and API tests**

```python
def test_bonus_approval_credits_bonus_balance_once():
    ...

def test_repair_approval_credits_cash_balance_once():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/services/test_bonus_grant_service.py tests/services/test_recharge_repair_service.py -q`
Expected: FAIL because services and endpoints do not exist yet

- [ ] **Step 3: Implement minimal services and route handlers**

```python
class BonusGrantService: ...
class RechargeRepairService: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/services/test_bonus_grant_service.py tests/services/test_recharge_repair_service.py tests/api/test_finance_bonus_grants.py tests/api/test_finance_recharge_repairs.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services app/api/routes/finance.py app/schemas tests/services tests/api
git commit -m "feat: add bonus grants and recharge repairs"
```

## Task 5: Make Finance Reports Cash/Bonus Aware

**Files:**
- Modify: `app/services/finance_report_service.py`
- Create: `tests/api/test_finance_reports.py`
- Create: `tests/services/test_finance_report_service.py`

- [ ] **Step 1: Write failing finance report tests**

```python
def test_finance_summary_excludes_bonus_when_requested():
    ...

def test_withdrawal_report_returns_cash_and_bonus_split():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/services/test_finance_report_service.py tests/api/test_finance_reports.py -q`
Expected: FAIL because reports still read plain recharge/withdrawal totals

- [ ] **Step 3: Implement split-aware report aggregation**

```python
def get_finance_summary(..., fund_scope: str = "all", include_bonus: bool = True) -> dict:
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/services/test_finance_report_service.py tests/api/test_finance_reports.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/finance_report_service.py tests/services/test_finance_report_service.py tests/api/test_finance_reports.py
git commit -m "feat: add cash bonus finance reporting"
```

## Task 6: Add Withdrawal Split Risk Fields And Duplicate Account Signals

**Files:**
- Modify: `app/db/models.py`
- Modify: `app/services/platform_withdrawal_service.py`
- Modify: `app/schemas/platform_withdrawals.py`
- Create: `tests/api/test_platform_withdrawals.py`
- Create: `tests/services/test_platform_withdrawal_service.py`

- [ ] **Step 1: Write failing withdrawal risk tests**

```python
def test_duplicate_withdraw_account_marks_request_and_lists_member_ids():
    ...

def test_rejected_withdrawal_restores_cash_bonus_split():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/services/test_platform_withdrawal_service.py tests/api/test_platform_withdrawals.py -q`
Expected: FAIL because duplicate account and split refund metadata do not exist

- [ ] **Step 3: Implement minimal risk metadata and serialization**

```python
duplicate_account_count = ...
risk_flags = ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/services/test_platform_withdrawal_service.py tests/api/test_platform_withdrawals.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/db/models.py app/services/platform_withdrawal_service.py app/schemas/platform_withdrawals.py tests/services/test_platform_withdrawal_service.py tests/api/test_platform_withdrawals.py
git commit -m "feat: add withdrawal split risk metadata"
```

## Task 7: Frontend Finance And Member Display Closure

**Files:**
- Modify: `frontend/src/pages/FinancePage.tsx`
- Create: `frontend/src/services/financeApi.ts`
- Create: `frontend/src/services/memberApi.ts`
- Create: `frontend/src/components/member/MemberIdLink.tsx`
- Create: `frontend/src/components/member/MemberProfilePopover.tsx`
- Create/modify finance pages under `frontend/src/pages/finance/`
- Modify: `frontend/src/routes/consoleRoutes.ts`

- [ ] **Step 1: Write failing frontend tests for real finance data and member-id display**

```tsx
test("finance page uses real api instead of mock data", async () => {
  ...
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- frontend/src/pages/...`
Expected: FAIL because finance pages still use mock rows

- [ ] **Step 3: Implement member id link and finance page data integration**

```tsx
export function MemberIdLink(...) { ... }
```

- [ ] **Step 4: Run tests and typecheck**

Run: `npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: connect finance ui and member id popovers"
```

## Task 8: Final Verification

**Files:**
- Verify all touched files above

- [ ] **Step 1: Run backend targeted suite**

Run: `python -m pytest tests/services/test_wallet_ledger_service.py tests/services/test_bonus_grant_service.py tests/services/test_recharge_repair_service.py tests/services/test_finance_report_service.py tests/services/test_platform_withdrawal_service.py tests/api/test_finance_bonus_grants.py tests/api/test_finance_recharge_repairs.py tests/api/test_finance_reports.py tests/api/test_platform_withdrawals.py -q`
Expected: PASS

- [ ] **Step 2: Run migration and invariant checks**

Run: `alembic upgrade head`
Expected: PASS

Run: `python scripts/check_wallet_balance_invariants.py`
Expected: PASS

- [ ] **Step 3: Run frontend verification**

Run: `cd frontend && npm run typecheck`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 4: Audit against document DoD**

Check each item in `whatsapp_bonus_repair_finance_member_plan_v2.md` section 15 against code, tests, and runtime evidence before declaring completion.

