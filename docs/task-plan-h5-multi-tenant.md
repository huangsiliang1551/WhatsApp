# H5 多租户管理系统（H5MT-001 ~ H5MT-008）

> **执行角色**: api_agent（后端）+ frontend_agent（前端）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 实现后台创建/管理多个 H5 前端站点，共享后端数据源，支持横向扩展部署

---

## 一、架构设计

### 核心思路

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  H5 站点 A  │     │  H5 站点 B  │     │  H5 站点 C  │
│  (渠道:微信) │     │  (渠道:抖音) │     │  (渠道:小红书)│
│  域名: a.com │     │  域名: b.com │     │  域名: c.com │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    VITE_API_BASE_URL
                           │
                    ┌──────┴──────┐
                    │   后端 API  │
                    │  (共享数据源) │
                    └─────────────┘
```

**关键原则**:
- **一个后端，N 个前端**: 所有 H5 站点共享同一个后端 API
- **site_key 隔离**: 每个 H5 站点有独立 site_key，数据按 site_key 过滤
- **静态部署**: 每个 H5 只是前端静态文件，部署到任意 CDN/静态主机
- **最小依赖**: H5 站点只需配置 `VITE_API_BASE_URL` + `VITE_SITE_KEY`
- **横向扩展**: 新增站点 = 复制前端模板 + 新 site_key + 新域名

### H5 站点生命周期

```
创建站点 → 配置域名/品牌 → 生成部署包 → 部署到CDN → 启用 → 投放渠道
     ↓                                              ↓
  后台管理 ←──── 数据分析 ←──── 用户访问 ←──── 渠道推广
```

---

## 二、后端增强（H5MT-001 ~ H5MT-004）

### H5MT-001：H5Site 模型增强

- **估计耗时**: 20 分钟

#### 新增迁移 0077

```python
# alembic/versions/20260616_0077_h5_site_enhancement.py

def upgrade():
    # 新增字段
    op.add_column("h5_sites", sa.Column("channel_type", sa.String(32), nullable=True))  # wechat/douyin/xiaohongshu/custom
    op.add_column("h5_sites", sa.Column("frontend_version", sa.String(32), nullable=True, server_default="1.0.0"))
    op.add_column("h5_sites", sa.Column("custom_theme_json", sa.JSON(), nullable=True))  # 自定义主题色/字体
    op.add_column("h5_sites", sa.Column("analytics_tracking_id", sa.String(64), nullable=True))
    op.add_column("h5_sites", sa.Column("deploy_url", sa.String(500), nullable=True))  # CDN 部署地址
    op.add_column("h5_sites", sa.Column("last_deployed_at", sa.DateTime(timezone=False), nullable=True))
    op.add_column("h5_sites", sa.Column("description", sa.String(500), nullable=True))
    
    # 索引
    op.create_index("ix_h5_sites_channel_type", "h5_sites", ["channel_type"])
    op.create_index("ix_h5_sites_status", "h5_sites", ["status"])
```

### H5MT-002：站点管理 API 完善

- **估计耗时**: 30 分钟

#### 新增端点

```python
# app/api/routes/platform.py 追加

@router.patch("/sites/{site_key}")
async def update_site(site_key, payload: H5SiteUpdateRequest, ...):
    """更新站点配置"""

@router.delete("/sites/{site_key}", status_code=204)
async def delete_site(site_key, ...):
    """删除站点（检查关联用户）"""

@router.patch("/sites/{site_key}/toggle")
async def toggle_site_status(site_key, payload: StatusToggleRequest, ...):
    """启用/停用站点"""

@router.get("/sites/{site_key}/analytics")
async def get_site_analytics(site_key, days=30, ...):
    """获取站点分析数据（用户数/注册/签到/任务完成）"""

@router.post("/sites/{site_key}/deploy")
async def deploy_site(site_key, ...):
    """生成部署信息（返回部署命令/CDN配置）"""
```

### H5MT-003：站点分析服务

- **估计耗时**: 30 分钟

```python
# app/services/h5_site_analytics_service.py

class H5SiteAnalyticsService:
    def get_analytics(self, site_key: str, days: int = 30) -> dict:
        """聚合站点数据"""
        return {
            "total_users": ...,           # 该站点注册用户总数
            "new_users_today": ...,       # 今日新注册
            "active_users_today": ...,    # 今日活跃
            "sign_in_count_today": ...,   # 今日签到数
            "task_completion_rate": ...,  # 任务完成率
            "revenue_today": ...,         # 今日充值金额
            "daily_trend": [...],         # 每日趋势（30天）
        }
```

### H5MT-004：站点数据隔离增强

- **估计耗时**: 20 分钟

确保所有 H5 相关 API 都通过 `site_key` 过滤数据：

| API | site_key 过滤 |
|-----|--------------|
| `/api/h5/auth/register` | 注册时写入 site_key |
| `/api/h5/auth/login` | 按 site_key 查询用户 |
| `/api/h5/tasks` | 按 site_key 过滤任务 |
| `/api/h5/wallet/*` | 按 site_key 过滤钱包 |
| `/api/h5/sign-in` | 按 site_key 过滤签到 |

---

## 三、前端站点管理增强（H5MT-005 ~ H5MT-008）

### H5MT-005：SitesPage 重写

- **估计耗时**: 60 分钟
- **目标行数**: ~400 行

```tsx
// frontend/src/pages/SitesPage.tsx 重写

export function SitesPage(): JSX.Element {
  return (
    <PageShell
      title="H5 站点管理"
      subtitle="管理多租户 H5 前端站点，支持横向扩展部署"
      stats={/* 站点数 / 启用数 / 总用户数 */}
      actions={/* 新建站点按钮 + 刷新 */}
    >
      {/* 站点卡片网格 */}
      <Row gutter={[16, 16]}>
        {sites.map(site => (
          <Col key={site.site_key} span={8}>
            <Card
              title={site.brand_name || site.site_key}
              extra={<Tag color={site.status === "active" ? "success" : "default"}>{site.status}</Tag>}
              actions={[
                <Button type="link" onClick={() => handleEdit(site)}>编辑</Button>,
                <Button type="link" onClick={() => handleToggle(site)}>
                  {site.status === "active" ? "停用" : "启用"}
                </Button>,
                <Dropdown menu={{ items: [
                  { key: "analytics", label: "查看分析", onClick: () => handleAnalytics(site) },
                  { key: "deploy", label: "部署信息", onClick: () => handleDeploy(site) },
                  { key: "copy-config", label: "复制配置", onClick: () => handleCopyConfig(site) },
                  { key: "delete", label: "删除", danger: true, onClick: () => handleDelete(site) },
                ]}}>
                  更多
                </Dropdown>,
              ]}
            >
              {/* 站点信息 */}
              <Descriptions column={1} size="small">
                <Descriptions.Item label="站点 Key">{site.site_key}</Descriptions.Item>
                <Descriptions.Item label="渠道">{site.channel_type || "-"}</Descriptions.Item>
                <Descriptions.Item label="域名">{site.domain || "-"}</Descriptions.Item>
                <Descriptions.Item label="部署地址">
                  {site.deploy_url ? <a href={site.deploy_url} target="_blank">{site.deploy_url}</a> : "-"}
                </Descriptions.Item>
                <Descriptions.Item label="前端版本">{site.frontend_version || "1.0.0"}</Descriptions.Item>
                <Descriptions.Item label="用户数">{site.user_count ?? "-"}</Descriptions.Item>
              </Descriptions>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 新建/编辑站点 Modal */}
      <Modal title={editingSite ? "编辑站点" : "新建 H5 站点"} ...>
        <Form form={form} layout="vertical">
          <Form.Item label="站点 Key" name="site_key" rules={[{ required: true }]}>
            <Input placeholder="唯一标识，如 wechat-channel-01" disabled={!!editingSite} />
          </Form.Item>
          <Form.Item label="品牌名称" name="brand_name">
            <Input placeholder="显示名称" />
          </Form.Item>
          <Form.Item label="渠道类型" name="channel_type">
            <Select options={[
              { label: "微信", value: "wechat" },
              { label: "抖音", value: "douyin" },
              { label: "小红书", value: "xiaohongshu" },
              { label: "自定义", value: "custom" },
            ]} />
          </Form.Item>
          <Form.Item label="域名" name="domain">
            <Input placeholder="h5.example.com" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item label="自定义主题" name="custom_theme_json">
            <TextArea rows={3} placeholder='{"primaryColor": "#1677ff", "logoUrl": ""}' />
          </Form.Item>
        </Form>
      </Modal>

      {/* 站点分析 Drawer */}
      <Drawer title={`${analyticsSite?.brand_name} 站点分析`} width={480} ...>
        <Descriptions column={2}>
          <Descriptions.Item label="总用户">{analytics.total_users}</Descriptions.Item>
          <Descriptions.Item label="今日新增">{analytics.new_users_today}</Descriptions.Item>
          <Descriptions.Item label="今日活跃">{analytics.active_users_today}</Descriptions.Item>
          <Descriptions.Item label="今日签到">{analytics.sign_in_count_today}</Descriptions.Item>
          <Descriptions.Item label="任务完成率">{analytics.task_completion_rate}%</Descriptions.Item>
          <Descriptions.Item label="今日充值">¥{analytics.revenue_today}</Descriptions.Item>
        </Descriptions>
        {/* 30天趋势图 */}
      </Drawer>

      {/* 部署信息 Modal */}
      <Modal title="部署信息" ...>
        <Alert message="部署命令" type="info" />
        <pre>
          {`# 1. 复制前端模板
cp -r frontend/dist h5-${deploySite.site_key}

# 2. 配置环境变量
echo "VITE_API_BASE_URL=http://your-backend:8000" > h5-${deploySite.site_key}/.env
echo "VITE_SITE_KEY=${deploySite.site_key}" >> h5-${deploySite.site_key}/.env

# 3. 部署到 CDN/静态主机
# (根据实际部署环境配置)`}
        </pre>
        <Button onClick={() => handleCopyDeployCommand(deploySite)}>复制部署命令</Button>
      </Modal>
    </PageShell>
  );
}
```

### H5MT-006：站点分析 API 层

- **估计耗时**: 15 分钟

```typescript
// frontend/src/services/siteApi.ts

export async function listSites(): Promise<H5Site[]>
export async function createSite(data: CreateSiteRequest): Promise<H5Site>
export async function updateSite(siteKey: string, data: UpdateSiteRequest): Promise<H5Site>
export async function deleteSite(siteKey: string): Promise<void>
export async function toggleSiteStatus(siteKey: string, status: string): Promise<void>
export async function getSiteAnalytics(siteKey: string, days?: number): Promise<SiteAnalytics>
export async function getDeployInfo(siteKey: string): Promise<DeployInfo>
```

### H5MT-007：站点数据隔离验证

- **估计耗时**: 20 分钟

验证所有 H5 API 都按 site_key 隔离数据：
- 不同 site_key 的用户互相不可见
- 不同 site_key 的签到/任务独立
- 钱包余额按 site_key 隔离

### H5MT-008：部署文档生成

- **估计耗时**: 15 分钟

在部署信息 Modal 中生成标准部署命令：

```bash
# 新增 H5 站点部署步骤

## 1. 创建站点（后台操作）
POST /api/platform/sites
Body: {"site_key": "wechat-01", "brand_name": "微信渠道", "channel_type": "wechat", "domain": "h5-wechat.example.com"}

## 2. 复制前端模板
cp -r frontend/dist/ h5-wechat-01/

## 3. 配置环境变量
cat > h5-wechat-01/.env << EOF
VITE_API_BASE_URL=https://api.example.com
VITE_SITE_KEY=wechat-01
EOF

## 4. 部署到 CDN
# Nginx 配置示例 / S3 上传 / Vercel 部署
```

---

## 四、验证标准

```
后端:
  GET /api/platform/sites → 200 + 站点列表
  POST /api/platform/sites → 201 + 创建站点
  PATCH /api/platform/sites/{key} → 200 + 更新
  DELETE /api/platform/sites/{key} → 204
  GET /api/platform/sites/{key}/analytics → 200 + 分析数据

前端:
  npm run build → 通过
  SitesPage: 卡片网格 + 创建/编辑/删除/启停/分析/部署
  站点分析 Drawer: 用户/签到/任务/充值数据

数据隔离:
  不同 site_key 用户互不可见
```

---

## 五、任务分配

| 任务 | 负责 | 文件 |
|------|------|------|
| H5MT-001 模型增强 | 后端 | 迁移 0077 |
| H5MT-002 API 完善 | 后端 | platform.py 追加 |
| H5MT-003 分析服务 | 后端 | h5_site_analytics_service.py |
| H5MT-004 数据隔离 | 后端 | 各 H5 API 增强 |
| H5MT-005 SitesPage 重写 | 前端 | ~400 行 |
| H5MT-006 站点 API 层 | 前端 | siteApi.ts |
| H5MT-007 数据隔离验证 | 测试 | E2E 验证 |
| H5MT-008 部署文档 | 后端 | 部署命令生成 |

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（H5 多租户轮）。请读取 docs/task-plan-h5-multi-tenant.md，一次性实现 H5MT-001 ~ H5MT-004 + H5MT-008 全部 5 个后端任务，不要中途暂停。

H5MT-001（模型增强）：
- 迁移 0077：h5_sites 新增 channel_type/frontend_version/custom_theme_json/analytics_tracking_id/deploy_url/last_deployed_at/description

H5MT-002（API 完善）：
- PATCH /api/platform/sites/{key} 更新
- DELETE /api/platform/sites/{key} 删除（检查关联用户）
- PATCH /api/platform/sites/{key}/toggle 启停
- GET /api/platform/sites/{key}/analytics 分析
- POST /api/platform/sites/{key}/deploy 部署信息

H5MT-003（分析服务）：
- H5SiteAnalyticsService: total_users/new_users_today/active_users_today/sign_in_count_today/task_completion_rate/revenue_today/daily_trend

H5MT-004（数据隔离）：
- 所有 /api/h5/* 端点按 site_key 过滤数据

H5MT-008（部署文档）：
- 生成标准部署命令模板

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（H5 站点管理轮）。请读取 docs/task-plan-h5-multi-tenant.md，一次性实现 H5MT-005 ~ H5MT-007 全部 3 个前端任务，不要中途暂停。

H5MT-005（SitesPage 重写 ~400行）：
- 站点卡片网格（site_key/品牌/渠道/域名/部署地址/版本/用户数）
- 新建/编辑 Modal（site_key/brand_name/channel_type/domain/description/custom_theme_json）
- 操作：编辑/启停/分析/部署/复制配置/删除
- 站点分析 Drawer（用户/签到/任务/充值 + 30天趋势）
- 部署信息 Modal（部署命令 + 复制按钮）

H5MT-006（站点 API 层）：
- siteApi.ts: listSites/createSite/updateSite/deleteSite/toggleSiteStatus/getSiteAnalytics/getDeployInfo

H5MT-007（数据隔离验证）：
- E2E 验证不同 site_key 数据隔离

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
