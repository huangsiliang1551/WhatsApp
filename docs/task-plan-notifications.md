# 通知中心完整实现方案（NOTIF-001 ~ NOTIF-005）

> **执行角色**: api_agent（后端）+ frontend_agent（前端）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 实现完整的通知系统：后端通知生成/存储/查询 + 前端通知页面 + 顶部铃铛弹出框

---

## 一、后端通知系统设计

### 1.1 数据模型

新增 `notifications` 表（Alembic 迁移 0074）：

```python
# alembic/versions/20260616_0074_notifications.py

def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_users.id"), nullable=True),  # 目标用户（可选，null=全局通知）
        sa.Column("type", sa.String(32), nullable=False),  # alert/info/warning/error
        sa.Column("category", sa.String(32), nullable=False),  # ai/queue/system/template/meta
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),  # info/warning/error/critical
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("action_url", sa.String(500), nullable=True),  # 点击跳转链接
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=False), nullable=True),
    )
    op.create_index("ix_notifications_account_unread", "notifications", ["account_id", "is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
```

### 1.2 通知类型定义

| type | category | 触发场景 | severity |
|------|----------|---------|----------|
| `alert` | `ai` | AI 回复失败/降级 | error |
| `alert` | `queue` | 队列积压超过阈值 | warning |
| `alert` | `queue` | 死信队列有新任务 | warning |
| `info` | `template` | 模板审核通过/拒绝 | info |
| `info` | `template` | 模板发送完成 | info |
| `alert` | `meta` | Meta API 错误/Token 过期 | error |
| `alert` | `meta` | Webhook 签名验证失败 | error |
| `info` | `system` | 用户注册/充值 | info |
| `alert` | `system` | 签到奖励发放 | info |
| `alert` | `system` | 邀请奖励发放 | info |
| `warning` | `system` | 商品任务余额不足 | warning |
| `info` | `system` | 商品包任务完成 | info |

### 1.3 通知服务

```python
# app/services/notification_service.py

class NotificationService:
    def __init__(self, session: Session):
        self._session = session

    def create_notification(
        self,
        account_id: str,
        type: str,
        category: str,
        title: str,
        message: str | None = None,
        severity: str = "info",
        user_id: str | None = None,
        action_url: str | None = None,
        metadata: dict | None = None,
    ) -> Notification:
        """创建通知记录"""
        notification = Notification(
            id=str(uuid.uuid4()),
            account_id=account_id,
            user_id=user_id,
            type=type,
            category=category,
            title=title,
            message=message,
            severity=severity,
            action_url=action_url,
            metadata_json=metadata,
        )
        self._session.add(notification)
        self._session.commit()
        return notification

    def list_notifications(
        self,
        account_id: str | None = None,
        user_id: str | None = None,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        """查询通知列表 + 总数"""
        query = select(Notification)
        if account_id:
            query = query.where(Notification.account_id == account_id)
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        total = self._session.scalar(select(func.count()).select_from(query.subquery())) or 0
        
        items = (
            self._session.execute(
                query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    def mark_as_read(self, notification_ids: list[str]) -> int:
        """标记通知为已读"""
        stmt = (
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .values(is_read=True, read_at=func.now())
        )
        result = self._session.execute(stmt)
        self._session.commit()
        return result.rowcount

    def mark_all_as_read(self, account_id: str, user_id: str | None = None) -> int:
        """全部标记为已读"""
        query = update(Notification).where(
            Notification.account_id == account_id,
            Notification.is_read == False,
        )
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        result = self._session.execute(query.values(is_read=True, read_at=func.now()))
        self._session.commit()
        return result.rowcount

    def get_unread_count(self, account_id: str, user_id: str | None = None) -> int:
        """获取未读数量"""
        query = select(func.count(Notification.id)).where(
            Notification.account_id == account_id,
            Notification.is_read == False,
        )
        if user_id:
            query = query.where(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        return self._session.scalar(query) or 0
```

### 1.4 API 端点

```python
# app/api/routes/notifications.py（重写）

@router.get("")
async def list_notifications(
    account_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    unread: bool | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: RequestActor = Depends(require_permission(Permission.AUDIT_READ)),
    session: Session = Depends(get_db_session),
) -> dict:
    if account_id:
        actor.require_account_access(account_id)
    svc = NotificationService(session)
    items, total = svc.list_notifications(
        account_id=account_id,
        user_id=user_id,
        unread_only=unread or False,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": n.id,
                "account_id": n.account_id,
                "type": n.type,
                "category": n.category,
                "title": n.title,
                "message": n.message,
                "severity": n.severity,
                "is_read": n.is_read,
                "action_url": n.action_url,
                "metadata": n.metadata_json,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

@router.get("/unread-count")
async def get_unread_count(
    account_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission(Permission.AUDIT_READ)),
    session: Session = Depends(get_db_session),
) -> dict:
    if account_id:
        actor.require_account_access(account_id)
    svc = NotificationService(session)
    count = svc.get_unread_count(account_id=account_id, user_id=user_id)
    return {"unread_count": count}

@router.post("/mark-read")
async def mark_as_read(
    notification_ids: list[str] = Body(...),
    actor: RequestActor = Depends(require_permission(Permission.AUDIT_READ)),
    session: Session = Depends(get_db_session),
) -> dict:
    svc = NotificationService(session)
    count = svc.mark_as_read(notification_ids)
    return {"marked_count": count}

@router.post("/mark-all-read")
async def mark_all_as_read(
    account_id: str = Query(...),
    user_id: str | None = Query(default=None),
    actor: RequestActor = Depends(require_permission(Permission.AUDIT_READ)),
    session: Session = Depends(get_db_session),
) -> dict:
    actor.require_account_access(account_id)
    svc = NotificationService(session)
    count = svc.mark_all_as_read(account_id=account_id, user_id=user_id)
    return {"marked_count": count}
```

### 1.5 通知触发集成

在关键业务节点调用 `NotificationService.create_notification()`：

| 触发位置 | 文件 | 通知内容 |
|---------|------|---------|
| AI 回复失败 | `task_engine.py` start_product 异常 | type=alert, category=ai, severity=error |
| 队列积压 | `task_scheduler.py` | type=alert, category=queue, severity=warning |
| 模板审核通过 | `template_service.py` | type=info, category=template |
| Meta API 错误 | `meta_account_registry.py` | type=alert, category=meta, severity=error |
| 商品任务完成 | `task_engine.py` complete_product | type=info, category=system |
| 商品任务余额不足 | `task_engine.py` InsufficientBalanceError | type=warning, category=system |

---

## 二、前端通知页面设计

### 2.1 NotificationsPage 重写

```tsx
// frontend/src/pages/NotificationsPage.tsx (~300行)

export function NotificationsPage(): JSX.Element {
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const { data, loading, reload } = usePageData({
    fetcher: () => listNotifications({ unread: filter === "unread" ? true : undefined }),
  });

  const notifications = data?.items ?? [];
  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <PageShell
      title="通知中心"
      subtitle={`共 ${data?.total ?? 0} 条通知，${unreadCount} 条未读`}
      actions={
        <Row justify="space-between" align="middle" style={{ flexWrap: "nowrap", width: "100%" }}>
          <Col>
            <Space>
              <Segmented
                options={[{ label: "全部", value: "all" }, { label: "未读", value: "unread" }]}
                value={filter}
                onChange={(v) => setFilter(v as "all" | "unread")}
              />
              <Select
                placeholder="分类筛选"
                allowClear
                style={{ width: 140 }}
                options={[
                  { label: "AI", value: "ai" },
                  { label: "队列", value: "queue" },
                  { label: "模板", value: "template" },
                  { label: "Meta", value: "meta" },
                  { label: "系统", value: "system" },
                ]}
                value={categoryFilter}
                onChange={setCategoryFilter}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <Button size="small" onClick={() => handleMarkAllRead()}>全部已读</Button>
              <Button size="small" icon={<ReloadOutlined />} onClick={reload} loading={loading}>刷新</Button>
            </Space>
          </Col>
        </Row>
      }
    >
      <List
        dataSource={filteredNotifications}
        loading={loading}
        renderItem={(n) => (
          <List.Item
            style={{ background: n.is_read ? "#fff" : "#f6ffed", padding: "12px 16px" }}
            actions={[
              !n.is_read && (
                <Button size="small" type="link" onClick={() => handleMarkRead(n.id)}>
                  标记已读
                </Button>
              ),
              n.action_url && (
                <Button size="small" type="link" onClick={() => handleNavigate(n.action_url!)}>
                  查看
                </Button>
              ),
            ]}
          >
            <List.Item.Meta
              avatar={getSeverityIcon(n.severity, n.category)}
              title={
                <Space>
                  <Tag color={getCategoryColor(n.category)}>{n.category}</Tag>
                  <Typography.Text strong={!n.is_read}>{n.title}</Typography.Text>
                </Space>
              }
              description={
                <Space direction="vertical" size={2}>
                  {n.message && <Typography.Text>{n.message}</Typography.Text>}
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                    {new Date(n.created_at!).toLocaleString("zh-CN")}
                  </Typography.Text>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </PageShell>
  );
}
```

### 2.2 顶部铃铛弹出框

在 `App.tsx` 中修改铃铛图标，增加 Popover 弹出框：

```tsx
// 替换现有的 BellOutlined（约 line 1128-1133）

<Popover
  content={
    <div style={{ width: 360, maxHeight: 400, overflow: "auto" }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 8 }}>
        <Col>
          <Typography.Text strong>通知</Typography.Text>
          {unreadCount > 0 && <Badge count={unreadCount} style={{ marginLeft: 8 }} />}
        </Col>
        <Col>
          <Button type="link" size="small" onClick={() => handleMarkAllRead()}>
            全部已读
          </Button>
        </Col>
      </Row>
      <Divider style={{ margin: "8px 0" }} />
      {recentNotifications.length === 0 ? (
        <div style={{ textAlign: "center", padding: 24, color: "#999" }}>
          暂无通知
        </div>
      ) : (
        <List
          size="small"
          dataSource={recentNotifications.slice(0, 5)}
          renderItem={(n) => (
            <List.Item
              style={{ padding: "8px 0", cursor: "pointer" }}
              onClick={() => {
                handleMarkRead(n.id);
                if (n.action_url) handleNavigate(n.action_url);
              }}
            >
              <List.Item.Meta
                avatar={getSeverityDot(n.severity)}
                title={
                  <Typography.Text ellipsis style={{ fontSize: 12 }}>
                    {n.title}
                  </Typography.Text>
                }
                description={
                  <Typography.Text type="secondary" style={{ fontSize: 10 }}>
                    {new Date(n.created_at!).toLocaleString("zh-CN")}
                  </Typography.Text>
                }
              />
              {!n.is_read && <Badge status="processing" />}
            </List.Item>
          )}
        />
      )}
      <Divider style={{ margin: "8px 0" }} />
      <div style={{ textAlign: "center" }}>
        <Button type="link" onClick={() => handleNavigate("/notifications")}>
          查看全部通知
        </Button>
      </div>
    </div>
  }
  trigger="click"
  placement="bottomRight"
>
  <Badge count={notificationCount} size="small" offset={[-4, 4]}>
    <BellOutlined style={{ fontSize: 18, cursor: "pointer", color: "#64748b" }} />
  </Badge>
</Popover>
```

### 2.3 通知轮询

在 App.tsx 中修改现有的通知轮询逻辑（约 line 533）：

```typescript
// 轮询未读数量 + 最近 5 条通知
useEffect(() => {
  const pollNotifications = async () => {
    try {
      const token = adminAuth.getAccessToken();
      if (!token) return;

      const [countRes, listRes] = await Promise.all([
        fetch(`${API_BASE}/api/notifications/unread-count`, {
          headers: { Authorization: `Bearer ${token}` },
        }).then(r => r.json()),
        fetch(`${API_BASE}/api/notifications?limit=5`, {
          headers: { Authorization: `Bearer ${token}` },
        }).then(r => r.json()),
      ]);

      setNotificationCount(countRes.unread_count ?? 0);
      setRecentNotifications(listRes.items ?? []);
    } catch {
      // 静默失败
    }
  };

  pollNotifications();
  const interval = setInterval(pollNotifications, 30000); // 30秒轮询
  return () => clearInterval(interval);
}, []);
```

---

## 三、任务分配

| 任务 | 负责 | 文件 |
|------|------|------|
| NOTIF-001 数据模型+迁移 | 后端 | `alembic/versions/20260616_0074_notifications.py` |
| NOTIF-002 通知服务 | 后端 | `app/services/notification_service.py` (~120行) |
| NOTIF-003 API 端点 | 后端 | `app/api/routes/notifications.py` (重写, ~100行) |
| NOTIF-004 通知触发集成 | 后端 | `task_engine.py` + `task_scheduler.py` + `template_service.py` |
| NOTIF-005 前端通知页面 | 前端 | `NotificationsPage.tsx` (重写, ~300行) |
| NOTIF-006 铃铛弹出框 | 前端 | `App.tsx` (修改 bell icon, ~60行) |
| NOTIF-007 通知轮询 | 前端 | `App.tsx` (修改轮询逻辑) |

---

## 四、验证标准

```
后端:
  GET /api/notifications?limit=5 → 200 + items
  GET /api/notifications/unread-count → 200 + {unread_count: N}
  POST /api/notifications/mark-read → 200 + {marked_count: N}
  触发 AI 失败 → notifications 表有新记录

前端:
  npm run build → 通过
  通知页面: 列表 + 筛选 + 标记已读 + 全部已读
  铃铛弹出框: 显示最近 5 条 + 未读数 + 查看全部链接
  30 秒轮询未读数量
```

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（通知系统轮）。请读取 docs/task-plan-notifications.md，一次性实现 NOTIF-001 ~ NOTIF-004 全部 4 个后端任务，不要中途暂停。

实现内容：

NOTIF-001（数据模型）：
- 新增 notifications 表（Alembic 迁移 0074）
- 字段：id/account_id/user_id/type/category/title/message/severity/is_read/action_url/metadata_json/created_at/read_at
- 索引：account_id+is_read, created_at

NOTIF-002（通知服务）：
- NotificationService: create_notification / list_notifications / mark_as_read / mark_all_as_read / get_unread_count
- 120 行

NOTIF-003（API 端点）：
- GET /api/notifications（列表+分页+筛选）
- GET /api/notifications/unread-count
- POST /api/notifications/mark-read
- POST /api/notifications/mark-all-read

NOTIF-004（通知触发集成）：
- task_engine.py: AI 回复失败 → 创建通知
- task_scheduler.py: 队列积压 → 创建通知
- task_engine.py: 商品任务完成 → 创建通知

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（通知页面轮）。请读取 docs/task-plan-notifications.md，一次性实现 NOTIF-005 ~ NOTIF-007 全部 3 个前端任务，不要中途暂停。

实现内容：

NOTIF-005（通知页面）：
- 重写 NotificationsPage.tsx (~300行)
- PageShell + 列表 + 已读/未读筛选 + 分类筛选
- 单条标记已读 + 全部已读 + 刷新

NOTIF-006（铃铛弹出框）：
- 修改 App.tsx 中的 BellOutlined（约 line 1128-1133）
- 改为 Popover 弹出框：最近 5 条通知 + 未读 badge + 全部已读 + 查看全部链接
- 点击通知 → 标记已读 + 跳转 action_url

NOTIF-007（通知轮询）：
- 修改 App.tsx 中的通知轮询（约 line 533）
- 轮询 /api/notifications/unread-count + /api/notifications?limit=5
- 30 秒间隔

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
