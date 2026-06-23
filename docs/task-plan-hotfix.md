# 遗留问题统一修复清单（HOTFIX-001 ~ HOTFIX-012）

> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 一次性修复所有已知断裂按钮、测试失败和视觉问题

---

## 问题总览

| 类别 | 数量 | 负责 |
|------|------|------|
| 🔴 前端断裂按钮（API 函数缺失） | 7 项 | 前端 Agent |
| 🔴 后端路由缺失 | 1 项 | 后端 Agent |
| 🟡 测试断言失效 | 4 项 | 前端 Agent |
| 🟡 测试环境超时 | 2 项 | 后端 Agent |
| ⚪ 视觉微调 | 2 项 | 前端 Agent |

---

## Part A：前端修复（11 项）

### HOTFIX-001：Dashboard 4 个 API 函数缺失

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 问题

DashboardPage 调用了 4 个 API 函数，但 `services/api.ts` 中未定义：
- `getDashboardSummary()` → `GET /api/dashboard/summary`
- `getDashboardTodo()` → `GET /api/dashboard/todo`
- `getAiPerformance()` → `GET /api/dashboard/ai-performance`
- `getTopIntents()` → `GET /api/dashboard/top-intents`

后端路由已存在（BFX 轮创建），仅缺前端函数。

#### 修复

在 `frontend/src/services/api.ts` 末尾添加：

```typescript
// ── Dashboard APIs ──

export async function getDashboardSummary(): Promise<DashboardSummaryResponse> {
  const response = await api.get<DashboardSummaryResponse>("/api/dashboard/summary");
  return response.data;
}

export async function getDashboardTodo(): Promise<DashboardTodoResponse> {
  const response = await api.get<DashboardTodoResponse>("/api/dashboard/todo");
  return response.data;
}

export async function getAiPerformance(params?: { days?: number }): Promise<AiPerformanceResponse> {
  const response = await api.get<AiPerformanceResponse>("/api/dashboard/ai-performance", { params });
  return response.data;
}

export async function getTopIntents(params?: { days?: number; limit?: number }): Promise<TopIntentsResponse> {
  const response = await api.get<TopIntentsResponse>("/api/dashboard/top-intents", { params });
  return response.data;
}
```

同时在文件顶部添加对应的 Response 类型定义。

#### 验收

1. DashboardPage 数据正常加载（不再 undefined）
2. `npm run build` 通过

---

### HOTFIX-002：UsersPage 删除用户 API 函数缺失

- **优先级**: P0
- **估计耗时**: 10 分钟

#### 问题

UsersPage 调用 `deletePlatformUser()`，但 api.ts 中无此函数。

#### 修复

在 `frontend/src/services/api.ts` 添加：

```typescript
export async function deletePlatformUser(userId: string): Promise<void> {
  await api.delete(`/api/platform/users/${userId}`);
}
```

同时确认 UsersPage.tsx 的 import 包含 `deletePlatformUser`。

#### 验收

1. 删除按钮点击后调用 API
2. `npm run build` 通过

---

### HOTFIX-003：ReviewsPage 3 个 API 函数缺失

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 问题

ReviewsPage 调用以下函数但 api.ts 中未定义：
- `updateReviewStatus(id, action)` → 单条审核
- `batchReviewAction(ids, action)` → 批量审核

#### 修复

先检查 ReviewsPage 实际 import 的函数名，然后在 api.ts 添加：

```typescript
export async function updateReviewStatus(
  reviewId: string,
  action: "approve" | "reject",
  payload?: { reviewer_note?: string }
): Promise<void> {
  await api.post(`/api/reviews/${reviewId}/${action}`, payload);
}

export async function batchReviewAction(
  reviewIds: string[],
  action: "approve" | "reject",
  payload?: { reviewer_note?: string }
): Promise<{ success_count: number; failed_count: number }> {
  const response = await api.post(`/api/reviews/batch-${action}`, {
    review_ids: reviewIds,
    ...payload,
  });
  return response.data;
}
```

#### 验收

1. 通过/驳回按钮可调用 API
2. 批量操作可用
3. `npm run build` 通过

---

### HOTFIX-004：admin-chat.test.tsx 4 个测试断言失效

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 问题

重构后 4 个测试失败（组件 DOM 结构变化导致断言不匹配）：

| 失败测试 | 原因 |
|---------|------|
| `MessagePanel > shows empty state when no conversation selected` | 空状态文案/结构改变 |
| `ContextPanel > shows empty state when no conversation` | 空状态文案/结构改变 |
| `ContextPanel > renders 4 tabs when conversation provided` | Tab 渲染方式改变 |
| `ContextPanel > shows handover button in operations tab` | 操作按钮 DOM 变化 |

#### 修复

更新 `frontend/src/pages/admin-chat.test.tsx`：

1. 读取当前 MessagePanel.tsx 和 ContextPanel.tsx 的实际 DOM 输出
2. 更新断言以匹配新组件结构
3. 确保 mock 覆盖所有新组件依赖

#### 验收

1. `npx vitest run --environment jsdom src/pages/admin-chat.test.tsx` → 12/12 通过
2. `npm run build` 通过

---

### HOTFIX-005：ContextPanel Tab 标签文案修复

- **优先级**: P1
- **估计耗时**: 10 分钟

#### 问题

之前 FX 轮修复了部分乱码，但 ContextPanel 的 Tab 标签可能仍有残余：
- "条" 应为 "客户"
- "历史" Tab 图标是否正确

#### 修复

检查 `frontend/src/pages/admin-chat/ContextPanel.tsx` 的 Tab items 定义，确认：
- Tab 1: "操作"（🎯 图标）
- Tab 2: "详情"（📋 图标）
- Tab 3: "客户"（👤 图标）— 确认不是"条"
- Tab 4: "历史"（📜 图标）

#### 验收

1. 4 个 Tab 文案正确
2. `npm run build` 通过

---

### HOTFIX-006：ConversationList 空状态残余

- **优先级**: P1
- **估计耗时**: 5 分钟

#### 问题

之前 FX 轮修复了 "条)条)" → "暂无会话"，但需确认：
- 空状态是否使用了 EmptyGuide 组件
- 是否显示引导操作（如 "模拟一条入站消息"）

#### 修复

检查 `frontend/src/pages/admin-chat/ConversationList.tsx` 的空状态渲染，确认使用 EmptyGuide 或至少显示友好文案。

#### 验收

1. 无会话时显示友好空状态
2. `npm run build` 通过

---

### HOTFIX-007：全量前端验证

- **优先级**: P0
- **估计耗时**: 10 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend
npx tsc --noEmit
npm run build
npx vitest run --environment jsdom src/pages/admin-chat.test.tsx
npx vitest run --environment jsdom src/pages/dashboardPage.test.tsx
npx vitest run --environment jsdom src/services/operations.test.ts
npx vitest run --environment jsdom src/pages/templatePage.test.tsx
npx vitest run --environment jsdom src/pages/metaAccountsPage.test.tsx
npx vitest run --environment jsdom src/pages/loginPage.test.tsx
npx vitest run --environment jsdom src/services/adminAuth.test.ts
npx vitest run --environment jsdom src/services/chatRealtime.test.ts
npx vitest run --environment jsdom src/pages/memberCustomerNavigation.test.tsx
```

#### 验收标准

| 项 | 预期 |
|----|------|
| tsc --noEmit | 0 errors |
| npm run build | 通过 |
| admin-chat.test.tsx | **12/12 通过**（修复后） |
| 其他测试 | 不退化 |

---

## Part B：后端修复（5 项）

### HOTFIX-008：deletePlatformUser 后端路由缺失

- **优先级**: P0
- **估计耗时**: 20 分钟

#### 问题

前端调用 `DELETE /api/platform/users/{userId}`，但后端无此路由。

#### 修复

在 `app/api/routes/platform.py` 添加：

```python
@router.delete("/api/platform/users/{user_id}")
async def delete_platform_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a platform user."""
    result = await session.execute(
        select(AppUser).where(AppUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(user)
    await session.commit()
    return Response(status_code=204)
```

#### 测试

在 `tests/test_conversations.py` 或新建 `tests/test_platform_users.py`：
- 删除存在的用户 → 204
- 删除不存在的用户 → 404

#### 验收

1. API 路由可用
2. 测试通过

---

### HOTFIX-009：Reviews 批量审核后端路由验证

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 问题

前端调用 `POST /api/reviews/batch-approve` 和 `POST /api/reviews/batch-reject`，需确认后端是否已有此路由。

#### 修复

1. 检查 `app/api/routes/reviews.py` 是否包含 batch 端点
2. 如果不存在，添加：

```python
@router.post("/api/reviews/batch-approve")
async def batch_approrove_reviews(
    payload: BatchReviewPayload,
    session: AsyncSession = Depends(get_session),
) -> BatchReviewResponse:
    ...

@router.post("/api/reviews/batch-reject")
async def batch_reject_reviews(
    payload: BatchReviewPayload,
    session: AsyncSession = Depends(get_session),
) -> BatchReviewResponse:
    ...
```

3. 同时确认单条审核路由 `POST /api/reviews/{id}/approve` 和 `POST /api/reviews/{id}/reject` 存在

#### 验收

1. 路由存在且可调用
2. 测试通过

---

### HOTFIX-010：测试环境超时问题标记

- **优先级**: P2
- **说明**: 以下测试需要 PostgreSQL 连接，在本地 SQLite 环境超时：
  - `test_customer_summary.py`（10 tests）
  - `test_conversation_notes.py`（7 tests）
  - 部分 `test_conversations.py` 用例

#### 建议

1. 为需要 PostgreSQL 的测试添加 `@pytest.mark.postgres` 标记
2. 在 `conftest.py` 中配置：无 PostgreSQL 时自动 skip
3. 或在 `pyproject.toml` 中添加 `pytest-postgresql` 依赖

**本轮不强制执行**，仅标记。

---

### HOTFIX-011：全量后端验证

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp
.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_log_sanitization.py tests/test_business_hours.py tests/test_canned_responses.py -q
```

#### 验收标准

| 项 | 预期 |
|----|------|
| test_health | 通过 |
| test_log_sanitization | 8/8 通过 |
| test_business_hours | 8/8 通过 |
| test_canned_responses | 8/8 通过 |

---

## Part C：Docker 重启验证（1 项）

### HOTFIX-012：Docker Compose 重启 + Launch Readiness 验证

- **优先级**: P0
- **估计耗时**: 10 分钟

#### 操作

```powershell
cd E:\codex\WhatsApp
docker compose restart app worker
# 等待 30 秒
docker compose ps
# 确认 7 个服务 healthy
curl http://localhost:8000/health
curl http://localhost:8000/api/launch-readiness
```

#### 验收标准

| 项 | 预期 |
|----|------|
| 7 服务 healthy | 确认 |
| /health 返回 200 | 确认 |
| Launch Readiness 文件检查 | 无假阳 Warning（BFX-001 修复已生效） |

---

## 执行顺序

```
前端 Agent: HOTFIX-001 → 002 → 003 → 004 → 005 → 006 → 007（验证）
后端 Agent: HOTFIX-008 → 009 → 011（验证）→ 012（Docker 重启）
```

前端和后端可**并行执行**，互不依赖。

---

## 全局约束

1. **前端不改后端**: 不改 `app/` 目录
2. **后端不改前端**: 不改 `frontend/` 目录
3. **不碰 H5**: 不改 `h5-member/` 目录
4. **每次改动后验证**: 前端 `npm run build`，后端 `pytest`
5. **一次性执行，不中途暂停**

---

## 发给前端会话的文本

```
你是管理后台前端 Agent（Hotfix 轮）。请读取 docs/task-plan-hotfix.md 的 Part A（HOTFIX-001 ~ HOTFIX-007），一次性执行全部 7 项修复，不要中途暂停确认。

核心修复：
1. HOTFIX-001: api.ts 添加 4 个 Dashboard API 函数（getDashboardSummary/getDashboardTodo/getAiPerformance/getTopIntents）
2. HOTFIX-002: api.ts 添加 deletePlatformUser 函数
3. HOTFIX-003: api.ts 添加 updateReviewStatus + batchReviewAction 函数
4. HOTFIX-004: 更新 admin-chat.test.tsx 断言（修复 4 个失败测试）
5. HOTFIX-005: 检查 ContextPanel Tab 文案（确认无乱码残余）
6. HOTFIX-006: 检查 ConversationList 空状态
7. HOTFIX-007: 全量验证（tsc + build + 全部测试）

硬约束：
1. 不改后端（app/ 目录）
2. 不碰 H5（h5-member/ 目录）
3. 每次改动后 npm run build 必须通过
4. admin-chat.test.tsx 最终必须 12/12 通过

进度写入 .codex-run/progress/HOTFIX-XXX.json。开始吧。
```

## 发给后端会话的文本

```
你是后端开发 Agent（Hotfix 轮）。请读取 docs/task-plan-hotfix.md 的 Part B（HOTFIX-008 ~ HOTFIX-012），一次性执行全部 5 项修复，不要中途暂停确认。

核心修复：
1. HOTFIX-008: 添加 DELETE /api/platform/users/{user_id} 路由（删除用户）
2. HOTFIX-009: 验证/添加 POST /api/reviews/batch-approve 和 batch-reject 路由
3. HOTFIX-010: 标记需要 PostgreSQL 的测试（添加 @pytest.mark.postgres，不强制）
4. HOTFIX-011: 全量后端验证（test_health + test_log_sanitization + test_business_hours + test_canned_responses）
5. HOTFIX-012: Docker Compose 重启 + Launch Readiness 验证

硬约束：
1. 不碰前端代码
2. 不碰 H5 相关路由
3. 每次改动后运行相关测试
4. 新增路由必须有测试覆盖

进度写入 .codex-run/progress/HOTFIX-XXX.json。开始吧。
```
