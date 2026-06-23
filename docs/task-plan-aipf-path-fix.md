# AI 提供商前端路径修复（AIPF-FIX-001）

> **执行角色**: frontend_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-13
> **总架构师签发**
> **目标**: 修复前后端 API 路径不匹配导致的 404 错误

---

## 问题

`frontend/src/services/aiProviderApi.ts` 中 4 处路径与后端不匹配：

| # | 前端当前路径 | 后端实际路径 | 修复 |
|---|-------------|------------|------|
| 1 | `GET /api/ai-providers/overrides` | `GET /api/ai-providers/account-overrides` | overrides → account-overrides |
| 2 | `PUT /api/ai-providers/overrides/${id}` | `PUT /api/ai-providers/account-overrides/${id}` | 同上 |
| 3 | `DELETE /api/ai-providers/overrides/${id}` | `DELETE /api/ai-providers/account-overrides/${id}` | 同上 |
| 4 | `POST /api/ai-providers/test-connection` | `POST /api/ai-providers/${id}/test` | 路径结构调整 |

## 修复

修改 `frontend/src/services/aiProviderApi.ts`：

```typescript
// 第 31 行: test-connection → {config_id}/test
// 改前:
const response = await api.post<TestConnectionResponse>("/api/ai-providers/test-connection", data);
// 改后:
const configId = data.config_id;
const response = await api.post<TestConnectionResponse>(`/api/ai-providers/${configId}/test`, data);

// 第 40 行: overrides → account-overrides
// 改前:
const response = await api.get<AccountOverride[]>("/api/ai-providers/overrides");
// 改后:
const response = await api.get<AccountOverride[]>("/api/ai-providers/account-overrides");

// 第 45 行: overrides → account-overrides
// 改前:
await api.put(`/api/ai-providers/overrides/${accountId}`, { provider_config_id: configId });
// 改后:
await api.put(`/api/ai-providers/account-overrides/${accountId}`, { provider_config_id: configId });

// 第 49 行: overrides → account-overrides
// 改前:
await api.delete(`/api/ai-providers/overrides/${accountId}`);
// 改后:
await api.delete(`/api/ai-providers/account-overrides/${accountId}`);
```

同时检查 `AIProvidersSettingsTab.tsx` 中调用 `testAIProviderConnection` 时是否传入了 `config_id` 字段。

## 验证

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
# 浏览器访问 /settings → AI 配置 Tab → 不再显示 404 错误
```

## 约束

1. 仅修改 `aiProviderApi.ts`（+ 必要时 `AIProvidersSettingsTab.tsx`）
2. 不改后端
3. 不改 H5
4. `npm run build` 必须通过
