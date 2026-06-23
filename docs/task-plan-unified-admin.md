# 统一后台架构方案（UNIFIED-ADMIN）

> **执行角色**: api_agent（后端）+ frontend_agent（前端）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-19
> **总架构师签发**
> **目标**: 将超管/代理商/下属三套后台统一为一套，通过权限控制菜单和数据

---

## 一、核心设计思路

### 当前架构（三套独立后台）

```
超管后台 (/)         → 42 个页面
代理商后台 (/agent/) → 12 个页面（~991 行）
下属工作台 (/workspace/) → 6 个页面（~675 行）

问题：
- 三套页面独立维护，改一个要改三处
- 代理商/下属页面是超管页面的简化副本
- 代码重复 ~1,666 行
```

### 目标架构（一套后台 + 权限控制）

```
统一后台 (/)
├── 所有角色使用同一套页面
├── 菜单按角色过滤（看不到 = 不存在）
├── 数据按角色隔离（代理商只看自己的）
├── 操作按权限控制（没权限 = 按钮不存在）
└── 修改一处 → 所有角色同时生效
```

### 角色权限矩阵

| 页面 | super_admin | agent | support | finance | manager |
|------|:-----------:|:-----:|:-------:|:-------:|:-------:|
| **工作台组** | | | | | |
| 概览 (dashboard) | ✅ | ✅ | ✅ | ✅ | ✅ |
| 会话工作台 (conversations) | ✅ | ✅ | ✅ | ❌ | ❌ |
| 会话分配 (assignments) | ✅ | ✅ | ✅ | ❌ | ❌ |
| 工单 (tickets) | ✅ | ✅ | ✅ | ❌ | ❌ |
| 客户 (customers) | ✅ | ✅ | ✅ | ✅ | ✅ |
| 审核队列 (reviews) | ✅ | ✅ | ❌ | ❌ | ✅ |
| **内容组** | | | | | |
| 模板消息 (templates) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 媒体库 (media) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 标签 (tags) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 商城数据 (ecommerce) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 任务规则 (task_rules) | ✅ | ✅ | ❌ | ❌ | ✅ |
| **人员组** | | | | | |
| 客服团队 (members) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 任务 (tasks) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 自动分配规则 (automation) | ❌ | ✅ | ❌ | ❌ | ✅ |
| 角色权限 (roles) | ❌ | ✅ | ❌ | ❌ | ❌ |
| **分析组** | | | | | |
| 报表中心 (reports) | ✅ | ✅ | ❌ | ✅ | ✅ |
| 运营看板 (operations) | ✅ | ✅ | ❌ | ✅ | ✅ |
| **系统组** | | | | | |
| Meta 账户 (meta) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 系统设置 (settings) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 安全中心 (security) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 通知中心 (notifications) | ✅ | ✅ | ❌ | ✅ | ✅ |
| **运维组** | | | | | |
| 监控健康 (monitoring) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 审计日志 (audit) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 告警中心 (alerts) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 通道事件 (provider_events) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 导入导出 (imports) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 站点管理 (sites) | ✅ | ✅ | ❌ | ❌ | ✅ |
| 代理商管理 (agents) | ✅ | ❌ | ❌ | ❌ | ❌ |
| H5 模板 (h5_templates) | ✅ | ✅ | ❌ | ❌ | ✅ |
| API 测试 (whatsapp_api_test) | ✅ | ❌ | ❌ | ❌ | ❌ |
| 链路调试 (debug_panel) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **专属功能** | | | | | |
| 账单管理 | ❌ | ✅ | ❌ | ✅ | ❌ |
| 个人中心 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 密码修改 | ❌ | ✅ | ✅ | ✅ | ✅ |

---

## 二、后端任务（UA-BE）

### UA-BE-001：权限 API（新增）

**新增**: `app/api/routes/permissions_api.py`

```python
@router.get("/api/auth/permissions")
async def get_current_permissions(actor: RequestActor):
    """返回当前用户的角色 + 可见菜单 + 操作权限"""
    return {
        "user_type": actor.user_type,  # super_admin / agent / agent_member
        "role": actor.role,            # admin / finance / manager / support
        "agency_id": actor.agency_id,  # 代理商 ID（超管为 null）
        "agency_name": actor.agency_name,
        "menus": get_visible_menus(actor),  # 可见菜单列表
        "permissions": get_permissions(actor),  # 操作权限列表
    }
```

### UA-BE-002：统一认证入口

**修改**: `app/api/routes/agent_auth.py` + `app/api/routes/workspace_auth.py`

合并为一个统一登录端点：

```python
@router.post("/api/auth/login")
async def unified_login(payload: LoginRequest):
    """统一登录：自动识别 super_admin / agent / agent_member"""
    user = authenticate(payload.username, payload.password)
    
    if user.user_type == "super_admin":
        token = create_token(user, user_type="super_admin")
    elif user.user_type == "agent":
        token = create_token(user, user_type="agent", agency_id=user.agency_id)
    elif user.user_type == "agent_member":
        member = get_member(user.id)
        token = create_token(user, user_type="agent_member",
                           agency_id=member.agency_id, role=member.role)
    
    return {"token": token, "user_type": user.user_type}
```

保留原有 `/api/admin-auth/login`、`/api/agent-auth/login`、`/api/workspace-auth/login` 向后兼容，内部调用统一登录逻辑。

### UA-BE-003：数据隔离统一中间件

**确保**: 所有 API 端点根据 actor 自动过滤数据（已在 AF-BE-001 中完成大部分）。

```python
# 通用数据过滤函数
def filter_by_actor(query, model, actor, agency_id_field="agency_id"):
    if actor.is_super_admin:
        return query  # 超管看全部
    elif actor.user_type in ("agent", "agent_member"):
        return query.where(getattr(model, agency_id_field) == actor.agency_id)
```

---

## 三、前端任务（UA-FE）

### UA-FE-001：权限状态管理

**新增**: `frontend/src/hooks/usePermissions.ts`

```typescript
interface UserPermissions {
  user_type: "super_admin" | "agent" | "agent_member";
  role: string;
  agency_id: string | null;
  agency_name: string | null;
  menus: string[];        // 可见菜单 ID 列表
  permissions: string[];  // 操作权限列表
}

export function usePermissions() {
  const [perms, setPerms] = useState<UserPermissions | null>(null);
  
  useEffect(() => {
    // 登录成功后调用 /api/auth/permissions
    fetch("/api/auth/permissions").then(r => r.json()).then(setPerms);
  }, []);
  
  const canSeeMenu = (menuId: string) => perms?.menus.includes(menuId) ?? false;
  const canDo = (permission: string) => perms?.permissions.includes(permission) ?? false;
  const isSuperAdmin = perms?.user_type === "super_admin";
  const isAgent = perms?.user_type === "agent";
  
  return { perms, canSeeMenu, canDo, isSuperAdmin, isAgent };
}
```

### UA-FE-002：统一登录页

**修改**: `frontend/src/pages/LoginPage.tsx`

```tsx
// 统一登录页，登录后根据 user_type 跳转
const handleLogin = async (values) => {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(values),
  });
  const { token, user_type } = await res.json();
  
  localStorage.setItem("auth_token", token);
  localStorage.setItem("user_type", user_type);
  
  // 所有角色统一跳转 /（主后台）
  navigate("/");
};
```

### UA-FE-003：菜单权限过滤

**修改**: `frontend/src/App.tsx`

```tsx
// 菜单渲染时过滤
const { canSeeMenu } = usePermissions();

const filteredRoutes = consoleRoutes.filter(route => {
  if (!route.visibleInNav) return false;
  return canSeeMenu(route.id);
});
```

### UA-FE-004：页面内权限控制

在每个页面中，根据权限控制操作按钮的显示：

```tsx
// 示例：ChatPage.tsx
const { canDo, isSuperAdmin, perms } = usePermissions();

// 超管看到代理商筛选器
{isSuperAdmin && (
  <Select placeholder="代理商" options={agencies} />
)}

// 代理商和客服看到自己的会话（无筛选器）
// 数据已在后端按 agency_id 过滤
```

### UA-FE-005：顶部用户信息显示

**修改**: `frontend/src/App.tsx`

```tsx
// 顶部右侧显示：用户名 + 角色标签 + 代理商名称（非超管时）
<Space>
  <Tag color="blue">{perms.role}</Tag>
  {perms.agency_name && <Tag>{perms.agency_name}</Tag>}
  <Dropdown menu={{ items: [
    { key: "profile", label: "个人中心", onClick: () => navigate("/profile") },
    { key: "password", label: "修改密码", onClick: () => setPasswordModalOpen(true) },
    { key: "logout", label: "登出", onClick: handleLogout },
  ]}}>
    <Avatar icon={<UserOutlined />} />
  </Dropdown>
</Space>
```

### UA-FE-006：统一登出

```tsx
const handleLogout = async () => {
  // 调用统一登出
  await fetch("/api/auth/logout", { method: "POST" });
  localStorage.removeItem("auth_token");
  localStorage.removeItem("user_type");
  navigate("/login");
};
```

### UA-FE-007：删除独立代理商/下属页面

**删除文件**（18 个，~1,666 行）：

```
frontend/src/pages/agent/AgentLayout.tsx
frontend/src/pages/agent/AgentLoginPage.tsx
frontend/src/pages/agent/AgentDashboardPage.tsx
frontend/src/pages/agent/AgentSitesPage.tsx
frontend/src/pages/agent/AgentMembersPage.tsx
frontend/src/pages/agent/AgentBillingPage.tsx
frontend/src/pages/agent/AgentTemplatePage.tsx
frontend/src/pages/agent/AgentProfilePage.tsx
frontend/src/pages/agent/AgentRolesPage.tsx
frontend/src/pages/agent/AgentAutomationPage.tsx
frontend/src/pages/agent/AgentSettingsPage.tsx
frontend/src/pages/agent/AgentConversationsPage.tsx
frontend/src/pages/workspace/WorkspaceLayout.tsx
frontend/src/pages/workspace/WorkspaceLoginPage.tsx
frontend/src/pages/workspace/WorkspaceDashboard.tsx
frontend/src/pages/workspace/WorkspaceConversations.tsx
frontend/src/pages/workspace/WorkspaceFinance.tsx
frontend/src/pages/workspace/WorkspaceSites.tsx
```

### UA-FE-008：删除独立路由

**修改**: `frontend/src/App.tsx`

```tsx
// 删除以下路由分支：
// - pathname.startsWith("/agent/") → renderAgentPage
// - pathname.startsWith("/workspace/") → renderWorkspacePage
// - pathname === "/agent/login"
// - pathname === "/workspace/login"

// 删除以下懒加载：
// - LazyAgentLayout, LazyAgentLoginPage, ...
// - LazyWorkspaceLayout, LazyWorkspaceLoginPage, ...
```

### UA-FE-009：专属功能整合

将代理商/下属专属功能整合到统一页面：

| 专属功能 | 整合到 | 条件显示 |
|---------|--------|---------|
| 代理商仪表盘数据 | DashboardPage | `isAgent` 时显示站点统计卡片 |
| 账单管理 | AgentsPage（新增 Tab） | `isAgent` 或 `role=finance` 时显示 |
| 个人中心 | 新增 ProfilePage | 所有角色可见 |
| 密码修改 | 顶部 Dropdown | 所有角色可见 |
| 下属管理 | AgentsPage（已有） | `isAgent` 时显示下属 Tab |

### UA-FE-010：账单管理整合

**修改**: `frontend/src/pages/AgentsPage.tsx`

```tsx
// 代理商登录时，不显示代理商列表，而是显示：
// Tab 1: 我的站点（复用 SitesPage 逻辑，只显示自己的）
// Tab 2: 下属管理（复用 AgentMembersPage 逻辑）
// Tab 3: 账单管理（复用 AgentBillingPage 逻辑）

// 超管登录时显示原有的代理商列表 + CRUD
```

或者新增一个 `MyWorkspacePage` 作为代理商/下属的个人工作台：

```tsx
// /my 路径（所有角色可访问）
// 超管：显示全局概览
// 代理商：显示我的站点 + 下属 + 账单
// 下属：显示我的角色信息 + 密码修改
```

---

## 四、任务清单

| # | 任务 | 类型 | 工作量 |
|---|------|------|--------|
| UA-BE-001 | 权限 API | 后端 | ~100 行 |
| UA-BE-002 | 统一认证入口 | 后端 | ~80 行 |
| UA-BE-003 | 数据隔离中间件完善 | 后端 | ~50 行 |
| UA-FE-001 | 权限状态管理 Hook | 前端 | ~60 行 |
| UA-FE-002 | 统一登录页 | 前端 | ~30 行修改 |
| UA-FE-003 | 菜单权限过滤 | 前端 | ~20 行修改 |
| UA-FE-004 | 页面内权限控制 | 前端 | ~100 行分散修改 |
| UA-FE-005 | 顶部用户信息 | 前端 | ~40 行修改 |
| UA-FE-006 | 统一登出 | 前端 | ~10 行修改 |
| UA-FE-007 | 删除独立页面（18 个） | 前端 | 删除 ~1,666 行 |
| UA-FE-008 | 删除独立路由 | 前端 | ~50 行删除 |
| UA-FE-009 | 专属功能整合 | 前端 | ~200 行 |
| UA-FE-010 | 账单管理整合 | 前端 | ~100 行 |

**总计**: 13 个任务（3 后端 + 10 前端）
**净效果**: 删除 ~1,666 行 + 新增 ~800 行 = **净减少 ~866 行**

---

## 五、登录流程

```
1. 所有角色访问 /login（统一登录页）
2. 输入用户名 + 密码
3. POST /api/auth/login
4. 后端返回 token + user_type
5. 前端存储 token → 跳转 /
6. 前端调用 GET /api/auth/permissions
7. 根据 permissions.menus 过滤菜单
8. 根据 permissions.permissions 过滤操作按钮
9. 后端 API 根据 token 中的 user_type + agency_id 过滤数据
```

---

## 六、执行顺序

```
Phase 1 (后端):
  UA-BE-001 权限 API
  UA-BE-002 统一认证入口
  UA-BE-003 数据隔离中间件完善

Phase 2 (前端):
  UA-FE-001 权限 Hook
  UA-FE-002 统一登录
  UA-FE-003 菜单过滤
  UA-FE-004 页面权限控制
  UA-FE-005 顶部用户信息
  UA-FE-006 统一登出
  UA-FE-009 专属功能整合
  UA-FE-010 账单整合

Phase 3 (清理):
  UA-FE-007 删除独立页面（18 个文件）
  UA-FE-008 删除独立路由
```

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（统一后台轮）。请读取 docs/task-plan-unified-admin.md，一次性实现 UA-BE-001 ~ UA-BE-003 全部 3 个后端任务，不要中途暂停。

UA-BE-001（权限 API）：
- GET /api/auth/permissions → 返回 user_type + role + agency_id + menus[] + permissions[]
- menus 列表根据 user_type + role 计算（参考文档中的角色权限矩阵）

UA-BE-002（统一认证入口）：
- POST /api/auth/login → 自动识别 super_admin/agent/agent_member
- POST /api/auth/logout → 统一登出
- 保留原有 3 个登录端点向后兼容

UA-BE-003（数据隔离中间件完善）：
- 确保所有 API 根据 actor 的 user_type + agency_id 自动过滤数据
- super_admin → 全部数据
- agent → 只看自己的
- agent_member → 按角色过滤

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（统一后台轮）。请读取 docs/task-plan-unified-admin.md，一次性实现 UA-FE-001 ~ UA-FE-010 全部 10 个前端任务，不要中途暂停。

核心任务：
1. usePermissions Hook（调用 /api/auth/permissions）
2. 统一登录（所有角色走同一个登录页）
3. 菜单按权限过滤（canSeeMenu）
4. 页面内操作按钮按权限控制（canDo）
5. 顶部显示用户名+角色+代理商名
6. 统一登出
7. 删除 agent/ 和 workspace/ 目录下 18 个文件（~1,666 行）
8. 删除 App.tsx 中的 renderAgentPage + renderWorkspacePage
9. 代理商专属功能整合到统一页面（仪表盘/账单/下属）
10. 个人中心 + 密码修改（所有角色可用）

约束：npm run build + 一次性完成。开始吧。
```
