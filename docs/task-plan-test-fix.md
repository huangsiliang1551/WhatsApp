# 测试修复方案（TEST-FIX）

> **执行角色**: api_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-19
> **总架构师签发**
> **目标**: 修复 Phase 4 下属工作台登录 + Phase 2 产品页面参数问题

---

## 一、BUG-1：下属成员登录端点（P0）

### 问题

`agency_members` 表中有客服/财务/经理用户记录，但后端没有对应的登录 API。当前只有：
- `/api/admin/auth/login` → 超管
- `/api/agent-auth/login` → 代理商管理员

### 修复方案

**新增**: `app/api/routes/workspace_auth.py`

```python
router = APIRouter(prefix="/api/workspace-auth", tags=["workspace-auth"])

@router.post("/login")
async def workspace_login(payload: WorkspaceLoginRequest):
    """下属成员登录"""
    # 1. 验证 username + password（admin_users 表，user_type="agent_member"）
    # 2. 查找 agency_members 记录，获取 agency_id + role
    # 3. 颁发 JWT token（含 agency_id, user_type="agent_member", role）
    # 4. 返回 token + 用户信息 + 角色

@router.get("/me")
async def workspace_me(actor: RequestActor):
    """当前下属信息"""
    # 返回：用户名 + 角色 + 代理商名称

@router.post("/logout")
async def workspace_logout():
    """登出"""

@router.post("/reset-password")
async def workspace_reset_password(actor: RequestActor, payload: ResetPasswordRequest):
    """修改密码"""
```

**注册**: `app/main.py` 增加 `app.include_router(workspace_auth_router)`

**JWT 颁发**:
```python
# token payload
{
    "sub": user_id,
    "user_type": "agent_member",
    "agency_id": agency_id,
    "role": "support",  # finance/manager/support
    "exp": datetime.utcnow() + timedelta(hours=24),
}
```

---

## 二、BUG-2：产品/商品包需要 account_id（P1）

### 问题

`/api/products` 和 `/api/product-packages` 需要 `account_id` 查询参数，超管端页面未传递。

### 修复方案

**前端**: `frontend/src/pages/EcommercePage.tsx` 或相关页面

```tsx
// 超管端调用时传递默认 account_id
const fetchProducts = async () => {
  const defaultAccountId = "acct-h5-daily-cn"; // 或使用第一个代理商的 account_id
  const data = await listProducts({ account_id: defaultAccountId });
  setProducts(data);
};
```

或后端增加超管端无需 account_id 的全局查询：

```python
# app/api/routes/products.py
@router.get("")
async def list_products(
    account_id: str | None = Query(None),
    actor: RequestActor = Depends(get_actor),
):
    if actor.user_type == "super_admin" and not account_id:
        # 超管不传 account_id 时返回所有产品
        query = select(Product)
    elif account_id:
        query = select(Product).where(Product.account_id == account_id)
    else:
        raise HTTPException(400, "account_id is required")
```

---

## 三、任务清单

| # | 任务 | 类型 | 优先级 |
|---|------|------|--------|
| TF-BE-001 | 下属登录端点 | 后端 | P0 |
| TF-BE-002 | 产品 API 超管免 account_id | 后端 | P1 |
| TF-FE-001 | WorkspaceLayout 登录对接 | 前端 | P0 |
| TF-FE-002 | 下属登出 + 密码修改对接 | 前端 | P0 |

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（测试修复轮）。请读取 docs/task-plan-test-fix.md，一次性修复 2 个 Bug。

TF-BE-001（P0，下属登录端点）：
- 新增 app/api/routes/workspace_auth.py
- POST /api/workspace-auth/login（验证 admin_users 表 user_type="agent_member"）
- GET /api/workspace-auth/me（返回用户信息+角色+代理商名称）
- POST /api/workspace-auth/logout
- POST /api/workspace-auth/reset-password
- JWT token 含：agency_id + user_type="agent_member" + role
- 在 main.py 注册路由

TF-BE-002（P1，产品 API 超管免 account_id）：
- 修改 products/product-packages 的 list 端点
- 超管不传 account_id 时返回所有数据

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（测试修复轮）。请读取 docs/task-plan-test-fix.md，一次性修复 2 个前端任务。

TF-FE-001（P0，下属登录对接）：
- WorkspaceLayout.tsx 调用 /api/workspace-auth/login
- 登录成功后跳转 /workspace/
- 存储 JWT token

TF-FE-002（P0，下属登出+密码修改对接）：
- WorkspaceLayout.tsx 登出调用 /api/workspace-auth/logout
- 密码修改调用 /api/workspace-auth/reset-password

约束：npm run build + 一次性完成。开始吧。
```
