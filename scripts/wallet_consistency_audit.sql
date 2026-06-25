-- =========================
-- 1. 钱包余额一致性校验
-- =========================
SELECT
  user_id,
  system_balance,
  system_cash_balance,
  system_bonus_balance,
  (system_cash_balance + system_bonus_balance) AS computed_balance
FROM wallet_accounts
WHERE system_balance != (system_cash_balance + system_bonus_balance);


-- =========================
-- 2. 冻结余额一致性
-- =========================
SELECT
  user_id,
  frozen_balance,
  system_cash_frozen,
  system_bonus_frozen,
  (system_cash_frozen + system_bonus_frozen) AS computed_frozen
FROM wallet_accounts
WHERE frozen_balance != (system_cash_frozen + system_bonus_frozen);


-- =========================
-- 3. 负余额检测（绝对禁止）
-- =========================
SELECT *
FROM wallet_accounts
WHERE system_cash_balance < 0
   OR system_bonus_balance < 0
   OR system_cash_frozen < 0
   OR system_bonus_frozen < 0;


-- =========================
-- 4. ledger缺失检测（最关键）
-- =========================
SELECT w.*
FROM wallet_accounts w
LEFT JOIN wallet_ledger_entries l
  ON w.account_id = l.account_id
 AND w.id = l.wallet_account_id
WHERE l.id IS NULL;


-- =========================
-- 5. 重复入账检测（幂等漏洞）
-- =========================
SELECT idempotency_key, COUNT(*) AS cnt
FROM wallet_ledger_entries
WHERE idempotency_key IS NOT NULL
GROUP BY idempotency_key
HAVING COUNT(*) > 1;


-- =========================
-- 6. 赠金未标记异常
-- =========================
SELECT *
FROM wallet_ledger_entries
WHERE source_type IN ('admin_bonus','invite_bonus','activity_bonus')
  AND is_bonus = false;


-- =========================
-- 7. 提现拆分异常
-- =========================
SELECT *
FROM withdrawal_requests
WHERE cash_amount + bonus_amount != amount;
