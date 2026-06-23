# H5 多租户系统 — 后端完整实现（H5MT-BE-FINAL）

> **执行角色**: api_agent + db_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 实现 H5 多租户后端完整功能：动态语言 + 预翻译表 + H5 来源追踪 + 站点权限 + 一键部署脚本

---

## 一、数据模型变更

### 1.1 新增表：h5_site_configs（独立配置）

```python
# alembic/versions/20260616_0077_h5_site_configs.py

class H5SiteConfig(Base, TimestampMixin):
    __tablename__ = "h5_site_configs"
    
    id = Column(String(36), primary_key=True, default=new_id)
    site_id = Column(String(36), ForeignKey("h5_sites.id"), nullable=False, unique=True)
    
    # 品牌配置
    logo_url = Column(String(500), nullable=True)
    favicon_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), nullable=True, default="#1677ff")
    font_family = Column(String(100), nullable=True)
    footer_text = Column(String(500), nullable=True)
    
    # 功能开关
    enabled_pages = Column(JSON, nullable=True)  # ["home", "tasks", "invite"]
    custom_css = Column(Text, nullable=True)
    
    # 部署配置
    deploy_type = Column(String(32), nullable=True)  # nginx/vercel/cdn
    ssh_host = Column(String(200), nullable=True)
    ssh_user = Column(String(50), nullable=True)
    ssh_key_path = Column(String(500), nullable=True)
    domain = Column(String(200), nullable=True)
    ssl_enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
```

### 1.2 新增表：h5_languages（动态语言）

```python
# alembic/versions/20260616_0078_h5_languages.py

class H5Language(Base, TimestampMixin):
    __tablename__ = "h5_languages"
    
    id = Column(String(36), primary_key=True, default=new_id)
    language_code = Column(String(10), nullable=False, unique=True)  # zh-CN, en-US, ja-JP
    display_name = Column(String(50), nullable=False)  # 中文、English、日本語
    flag_emoji = Column(String(10), nullable=True)  # 🇨🇳 🇺🇸 🇯🇵
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
```

### 1.3 新增表：h5_translations（预翻译表）

```python
# alembic/versions/20260616_0079_h5_translations.py

class H5Translation(Base, TimestampMixin):
    __tablename__ = "h5_translations"
    
    id = Column(String(36), primary_key=True, default=new_id)
    site_id = Column(String(36), ForeignKey("h5_sites.id"), nullable=False)
    language_code = Column(String(10), nullable=False)
    translation_key = Column(String(200), nullable=False)  # "common.submit", "task.title"
    translated_text = Column(Text, nullable=False)
    is_ai_translated = Column(Boolean, default=False)  # AI 翻译标记
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint("site_id", "language_code", "translation_key", name="uq_h5_translation"),
        Index("ix_h5_translation_site_lang", "site_id", "language_code"),
    )
```

### 1.4 新增表：site_permissions（站点权限）

```python
# alembic/versions/20260616_0080_site_permissions.py

class SitePermission(Base, TimestampMixin):
    __tablename__ = "site_permissions"
    
    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), ForeignKey("admin_users.id"), nullable=False)
    site_id = Column(String(36), ForeignKey("h5_sites.id"), nullable=False)
    role = Column(String(32), nullable=False)  # admin/editor/analyst/support
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("user_id", "site_id", name="uq_site_permission"),
        Index("ix_site_permission_user", "user_id"),
        Index("ix_site_permission_site", "site_id"),
    )
```

### 1.5 模型增强：Conversation/Ticket/TaskInstance 增加 site_key

```python
# alembic/versions/20260616_0081_h5_source_tracking.py

# Conversation 增加 site_key
op.add_column("conversations", sa.Column("site_key", sa.String(50), nullable=True))
op.create_index("ix_conversations_site_key", "conversations", ["site_key"])

# Ticket 增加 site_key
op.add_column("tickets", sa.Column("site_key", sa.String(50), nullable=True))
op.create_index("ix_tickets_site_key", "tickets", ["site_key"])

# TaskInstance 增加 site_key
op.add_column("mkt_task_instances", sa.Column("site_key", sa.String(50), nullable=True))
op.create_index("ix_mkt_task_instances_site_key", "mkt_task_instances", ["site_key"])
```

### 1.6 新增表：audit_logs（完整审计）

```python
# alembic/versions/20260616_0082_audit_logs_enhancement.py

# 增强现有 audit_logs 表
op.add_column("audit_logs", sa.Column("ip_address", sa.String(45), nullable=True))
op.add_column("audit_logs", sa.Column("user_agent", sa.String(500), nullable=True))
op.add_column("audit_logs", sa.Column("action_type", sa.String(32), nullable=True))  # create/read/update/delete/deploy
op.create_index("ix_audit_logs_action_type", "audit_logs", ["action_type"])
op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])
```

---

## 二、后端服务实现

### 2.1 H5 语言管理服务

```python
# app/services/h5_language_service.py (~150行)

class H5LanguageService:
    def __init__(self, session: Session):
        self._session = session

    def list_languages(self) -> list[H5Language]:
        """列出所有语言"""
        return self._session.scalars(
            select(H5Language).order_by(H5Language.is_default.desc(), H5Language.display_name)
        ).all()

    def create_language(self, language_code: str, display_name: str, flag_emoji: str | None = None) -> H5Language:
        """创建新语言"""
        lang = H5Language(
            id=str(uuid.uuid4()),
            language_code=language_code,
            display_name=display_name,
            flag_emoji=flag_emoji,
        )
        self._session.add(lang)
        self._session.commit()
        return lang

    def update_language(self, language_id: str, **kwargs) -> H5Language:
        """更新语言"""
        lang = self._session.get(H5Language, language_id)
        if not lang:
            raise LookupError(f"Language '{language_id}' not found.")
        for key, value in kwargs.items():
            if hasattr(lang, key):
                setattr(lang, key, value)
        self._session.commit()
        return lang

    def delete_language(self, language_id: str) -> None:
        """删除语言（检查是否被使用）"""
        lang = self._session.get(H5Language, language_id)
        if not lang:
            raise LookupError(f"Language '{language_id}' not found.")
        
        # 检查是否有翻译使用此语言
        count = self._session.scalar(
            select(func.count(H5Translation.id)).where(
                H5Translation.language_code == lang.language_code
            )
        ) or 0
        if count > 0:
            raise ValueError(f"Cannot delete language '{lang.display_name}': {count} translations exist.")
        
        self._session.delete(lang)
        self._session.commit()

    def set_default_language(self, language_id: str) -> None:
        """设置默认语言"""
        # 先取消所有默认
        self._session.execute(
            update(H5Language).values(is_default=False)
        )
        # 设置新默认
        lang = self._session.get(H5Language, language_id)
        if not lang:
            raise LookupError(f"Language '{language_id}' not found.")
        lang.is_default = True
        self._session.commit()
```

### 2.2 翻译服务（AI 兜底）

```python
# app/services/h5_translation_service.py (~200行)

class H5TranslationService:
    def __init__(self, session: Session, ai_provider: AIProvider | None = None):
        self._session = session
        self._ai_provider = ai_provider

    def get_translations(self, site_id: str, language_code: str) -> dict[str, str]:
        """获取站点指定语言的所有翻译"""
        translations = self._session.scalars(
            select(H5Translation).where(
                H5Translation.site_id == site_id,
                H5Translation.language_code == language_code,
            )
        ).all()
        return {t.translation_key: t.translated_text for t in translations}

    def translate_key(
        self,
        site_id: str,
        language_code: str,
        translation_key: str,
        source_text: str,
    ) -> str:
        """翻译单个 key（优先查表，否则 AI 翻译）"""
        # 1. 先查表
        existing = self._session.scalar(
            select(H5Translation).where(
                H5Translation.site_id == site_id,
                H5Translation.language_code == language_code,
                H5Translation.translation_key == translation_key,
            )
        )
        if existing:
            return existing.translated_text
        
        # 2. AI 翻译
        if not self._ai_provider:
            raise ValueError("No AI provider configured for translation.")
        
        # 调用 AI 翻译
        prompt = f"Translate the following text to {language_code}. Only return the translated text, no explanation.\n\nText: {source_text}"
        translated = self._ai_provider.generate(prompt)
        
        # 3. 存入翻译表
        translation = H5Translation(
            id=str(uuid.uuid4()),
            site_id=site_id,
            language_code=language_code,
            translation_key=translation_key,
            translated_text=translated,
            is_ai_translated=True,
        )
        self._session.add(translation)
        self._session.commit()
        
        return translated

    def batch_translate(
        self,
        site_id: str,
        language_code: str,
        translations: dict[str, str],  # key -> source_text
    ) -> dict[str, str]:
        """批量翻译"""
        result = {}
        for key, source_text in translations.items():
            result[key] = self.translate_key(site_id, language_code, key, source_text)
        return result
```

### 2.3 站点权限服务

```python
# app/services/site_permission_service.py (~120行)

class SitePermissionService:
    def __init__(self, session: Session):
        self._session = session

    def get_user_permissions(self, user_id: str) -> list[SitePermission]:
        """获取用户的所有站点权限"""
        return self._session.scalars(
            select(SitePermission).where(SitePermission.user_id == user_id)
        ).all()

    def get_site_permissions(self, site_id: str) -> list[SitePermission]:
        """获取站点的所有权限"""
        return self._session.scalars(
            select(SitePermission).where(SitePermission.site_id == site_id)
        ).all()

    def grant_permission(self, user_id: str, site_id: str, role: str) -> SitePermission:
        """授予权限"""
        perm = SitePermission(
            id=str(uuid.uuid4()),
            user_id=user_id,
            site_id=site_id,
            role=role,
        )
        self._session.add(perm)
        self._session.commit()
        return perm

    def revoke_permission(self, permission_id: str) -> None:
        """撤销权限"""
        perm = self._session.get(SitePermission, permission_id)
        if not perm:
            raise LookupError(f"Permission '{permission_id}' not found.")
        self._session.delete(perm)
        self._session.commit()

    def update_role(self, permission_id: str, role: str) -> SitePermission:
        """更新角色"""
        perm = self._session.get(SitePermission, permission_id)
        if not perm:
            raise LookupError(f"Permission '{permission_id}' not found.")
        perm.role = role
        self._session.commit()
        return perm

    def check_permission(self, user_id: str, site_id: str, required_role: str) -> bool:
        """检查用户是否有指定站点的权限"""
        perm = self._session.scalar(
            select(SitePermission).where(
                SitePermission.user_id == user_id,
                SitePermission.site_id == site_id,
            )
        )
        if not perm:
            return False
        
        # 角色层级：admin > editor > analyst > support
        role_hierarchy = {"admin": 4, "editor": 3, "analyst": 2, "support": 1}
        return role_hierarchy.get(perm.role, 0) >= role_hierarchy.get(required_role, 0)
```

### 2.4 部署脚本生成服务

```python
# app/services/h5_deploy_service.py (~150行)

class H5DeployService:
    def generate_deploy_script(self, site: H5Site, config: H5SiteConfig) -> str:
        """生成一键部署脚本"""
        script = f"""#!/bin/bash
# H5 站点一键部署脚本
# 站点: {site.brand_name} ({site.site_key})
# 生成时间: {datetime.now().isoformat()}

set -e

echo "=== H5 站点部署: {site.brand_name} ==="

# 1. 安装依赖
echo "[1/6] 安装依赖..."
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

# 2. 配置 Nginx
echo "[2/6] 配置 Nginx..."
cat > /etc/nginx/sites-available/{site.site_key} << 'NGINX'
server {{
    listen 80;
    server_name {config.domain};

    root /var/www/{site.site_key};
    index index.html;

    location / {{
        try_files $uri $uri/ /index.html;
    }}

    # API 代理（隐藏后端真实 IP）
    location /api/ {{
        proxy_pass http://YOUR_BACKEND_IP:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
NGINX

ln -sf /etc/nginx/sites-available/{site.site_key} /etc/nginx/sites-enabled/

# 3. 部署前端文件
echo "[3/6] 部署前端文件..."
mkdir -p /var/www/{site.site_key}
# TODO: 从构建服务器拉取前端文件
# wget -O /tmp/h5-bundle.tar.gz http://build-server/h5-{site.site_key}.tar.gz
# tar -xzf /tmp/h5-bundle.tar.gz -C /var/www/{site.site_key}

# 4. 配置环境变量
echo "[4/6] 配置环境变量..."
cat > /var/www/{site.site_key}/.env << 'ENV'
VITE_API_BASE_URL=/api
VITE_SITE_KEY={site.site_key}
ENV

# 5. 申请 SSL 证书
echo "[5/6] 申请 SSL 证书..."
certbot --nginx -d {config.domain} --non-interactive --agree-tos --email YOUR_EMAIL

# 6. 重启 Nginx
echo "[6/6] 重启 Nginx..."
systemctl restart nginx

echo "=== 部署完成 ==="
echo "访问地址: https://{config.domain}"
"""
        return script

    def verify_deployment(self, site: H5Site, config: H5SiteConfig) -> dict:
        """验证部署状态"""
        import httpx
        results = {
            "domain_accessible": False,
            "ssl_valid": False,
            "api_proxy_working": False,
        }
        
        try:
            # 检查域名可访问
            resp = httpx.get(f"https://{config.domain}", timeout=10)
            results["domain_accessible"] = resp.status_code == 200
            results["ssl_valid"] = True  # https 成功即 SSL 有效
        except Exception as e:
            results["error"] = str(e)
        
        try:
            # 检查 API 代理
            resp = httpx.get(f"https://{config.domain}/api/health", timeout=10)
            results["api_proxy_working"] = resp.status_code == 200
        except Exception:
            pass
        
        return results
```

---

## 三、API 端点

### 3.1 语言管理 API

```python
# app/api/routes/h5_languages.py

@router.get("/languages")
async def list_languages():
    """列出所有语言"""

@router.post("/languages")
async def create_language(payload: CreateLanguageRequest):
    """创建新语言"""

@router.patch("/languages/{language_id}")
async def update_language(language_id: str, payload: UpdateLanguageRequest):
    """更新语言"""

@router.delete("/languages/{language_id}", status_code=204)
async def delete_language(language_id: str):
    """删除语言"""

@router.post("/languages/{language_id}/set-default")
async def set_default_language(language_id: str):
    """设置默认语言"""
```

### 3.2 翻译 API

```python
# app/api/routes/h5_translations.py

@router.get("/sites/{site_id}/translations/{language_code}")
async def get_translations(site_id: str, language_code: str):
    """获取站点翻译"""

@router.post("/sites/{site_id}/translations/{language_code}")
async def translate_key(site_id: str, language_code: str, payload: TranslateKeyRequest):
    """翻译单个 key（AI 兜底）"""

@router.post("/sites/{site_id}/translations/{language_code}/batch")
async def batch_translate(site_id: str, language_code: str, payload: BatchTranslateRequest):
    """批量翻译"""
```

### 3.3 站点权限 API

```python
# app/api/routes/site_permissions.py

@router.get("/users/{user_id}/permissions")
async def get_user_permissions(user_id: str):
    """获取用户权限"""

@router.get("/sites/{site_id}/permissions")
async def get_site_permissions(site_id: str):
    """获取站点权限"""

@router.post("/permissions")
async def grant_permission(payload: GrantPermissionRequest):
    """授予权限"""

@router.delete("/permissions/{permission_id}", status_code=204)
async def revoke_permission(permission_id: str):
    """撤销权限"""

@router.patch("/permissions/{permission_id}")
async def update_permission_role(permission_id: str, payload: UpdateRoleRequest):
    """更新角色"""
```

### 3.4 部署 API

```python
# app/api/routes/h5_deploy.py

@router.post("/sites/{site_id}/deploy-script")
async def generate_deploy_script(site_id: str):
    """生成部署脚本"""

@router.post("/sites/{site_id}/verify-deployment")
async def verify_deployment(site_id: str):
    """验证部署状态"""
```

---

## 四、数据自动填充

### 4.1 Conversation.site_key 自动填充

在创建会话时，从 customer_id 关联查询 AppUser.registration_site_id：

```python
# app/services/conversation_service.py 修改

async def create_conversation(self, customer_id: str, ...):
    # 查询用户注册站点
    user = self._session.scalar(
        select(AppUser).where(AppUser.public_user_id == customer_id)
    )
    site_key = user.registration_site_id if user else None
    
    conv = Conversation(
        ...
        site_key=site_key,  # 自动填充
    )
    self._session.add(conv)
```

### 4.2 Ticket/TaskInstance 同理

在创建时自动填充 `site_key`。

---

## 五、任务清单

| 任务 | 文件 | 行数 |
|------|------|------|
| 迁移 0077-0082 | alembic/versions/ | ~200 行 |
| H5LanguageService | app/services/h5_language_service.py | ~150 行 |
| H5TranslationService | app/services/h5_translation_service.py | ~200 行 |
| SitePermissionService | app/services/site_permission_service.py | ~120 行 |
| H5DeployService | app/services/h5_deploy_service.py | ~150 行 |
| 语言 API | app/api/routes/h5_languages.py | ~80 行 |
| 翻译 API | app/api/routes/h5_translations.py | ~80 行 |
| 权限 API | app/api/routes/site_permissions.py | ~80 行 |
| 部署 API | app/api/routes/h5_deploy.py | ~60 行 |
| Conversation/Ticket/TaskInstance 自动填充 site_key | 各 service | ~50 行 |
| **总计** | | ~1500 行 |

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（H5 多租户最终轮）。请读取 docs/task-plan-h5-mt-backend-final.md，一次性实现全部后端任务，不要中途暂停。

核心任务：

1. 数据模型（迁移 0077-0082）：
   - h5_site_configs（独立配置表）
   - h5_languages（动态语言表）
   - h5_translations（预翻译表，AI 翻译标记）
   - site_permissions（4 角色权限）
   - Conversation/Ticket/TaskInstance 增加 site_key 冗余字段
   - audit_logs 增强（ip_address/user_agent/action_type）

2. 服务层（4 个服务）：
   - H5LanguageService（CRUD + 设置默认）
   - H5TranslationService（查表优先 + AI 翻译兜底）
   - SitePermissionService（4 角色：admin/editor/analyst/support）
   - H5DeployService（生成 Nginx + Let's Encrypt 一键脚本）

3. API 端点（4 组）：
   - 语言管理 API（5 端点）
   - 翻译 API（3 端点）
   - 站点权限 API（5 端点）
   - 部署 API（2 端点）

4. 数据自动填充：
   - Conversation/Ticket/TaskInstance 创建时自动填充 site_key

约束：重启 Docker 验证 API。开始吧。
```
