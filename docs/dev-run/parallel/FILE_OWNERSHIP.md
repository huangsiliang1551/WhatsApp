# FILE_OWNERSHIP

并行线程必须遵守文件边界。

## W0 共享基础

可改：

```text
app/db/models.py
alembic/versions/**
app/core/settings.py
app/core/permission_defs.py
pyproject.toml
.github/workflows/**
app/main.py
```

W0 先执行。W1-W6 不应直接改这些共享文件，除非当前状态文件明确允许。

## W1 P0资金

可改：

```text
app/core/production_guard.py
app/services/wallet_*.py
app/services/payment_*.py
app/services/recharge_repair_service.py
app/services/platform_withdrawal_service.py
app/services/withdrawal_*.py
app/api/routes/payment_callback.py
app/api/routes/finance.py
app/api/routes/platform_withdrawals.py
scripts/check_*wallet*.py
scripts/*reconcile*.py
tests/services/test_wallet_*.py
tests/services/test_payment_*.py
tests/services/test_withdrawal_*.py
tests/api/test_payment_*.py
tests/api/test_platform_withdrawal_*.py
```

## W2 WhatsApp号码池

可改：

```text
app/services/site_whatsapp_phone_pool_service.py
app/services/whatsapp_*service.py
app/services/whatsapp_inbound_command_router.py
app/services/h5_member_whatsapp_binding_service.py
app/api/routes/whatsapp_auth_h5.py
app/api/routes/whatsapp_auth_admin.py
app/api/routes/h5_member_whatsapp_binding.py
app/schemas/whatsapp*.py
tests/services/test_whatsapp_*.py
tests/api/test_whatsapp_*.py
tests/api/test_h5_whatsapp_*.py
```

不得直接改 `app/api/routes/webhooks.py`，只提供 router service；W9 接线。

## W3 权限数据漏斗

可改：

```text
app/services/effective_access_service.py
app/services/data_scope_filter_service.py
app/services/*ownership*.py
app/services/*handover*.py
app/api/routes/permissions_api.py
app/api/routes/site_permissions.py
app/schemas/permissions*.py
tests/services/test_permission*.py
tests/api/test_permissions*.py
tests/api/test_data_scope*.py
```

不得把前端菜单重构作为主任务。

## W4 H5网关

可改：

```text
app/services/h5_gateway_*.py
app/api/routes/h5_gateway_*.py
app/api/routes/h5_deploy.py
app/services/h5_deploy_service.py
deploy/h5-gateway/**
tools/codex/**
scripts/h5_gateway_*.py
tests/services/test_h5_gateway_*.py
tests/api/test_h5_gateway_*.py
```

## W5 前端

可改：

```text
frontend/src/pages/**/*WhatsApp*.tsx
frontend/src/pages/**/*Gateway*.tsx
frontend/src/pages/**/*Permission*.tsx
frontend/src/pages/**/*Finance*.tsx
frontend/src/pages/**/*Sites*.tsx
frontend/src/services/*whatsapp*.ts
frontend/src/services/*gateway*.ts
frontend/src/types/*whatsapp*.ts
frontend/src/types/*gateway*.ts
frontend/src/components/whatsapp/**
frontend/src/components/h5-gateway/**
```

不得直接改 `frontend/src/routes/consoleRoutes.ts`，由 W9 统一接线。

## W6 测试

可改：

```text
tests/e2e/**
tests/integration/**
tests/conftest.py
scripts/run_p0_e2e_smoke.py
docs/dev-run/TEST_LOG.md
```

## W9 集成

最终接线可改：

```text
app/main.py
app/api/deps.py
app/api/routes/webhooks.py
app/core/permission_defs.py
frontend/src/routes/consoleRoutes.ts
pyproject.toml
.github/workflows/**
alembic/versions/**
```
