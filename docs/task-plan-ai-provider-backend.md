# 动态 AI 提供商管理 — 后端任务（AIP-001 ~ AIP-005）

> **执行角色**: api_agent + db_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-13
> **总架构师签发**
> **目标**: 实现动态 AI 提供商管理，支持后台 CRUD 任意 OpenAI 兼容 API

---

## 背景

当前 AI 配置硬编码在 `.env`，仅支持 OpenAI + DeepSeek，变更需重启容器。本任务实现数据库存储 AI 配置，后台自由增删改，无需重启。

核心洞察：DeepSeek/Groq/Ollama/Together AI 等均兼容 OpenAI SDK `chat.completions.create()`，只需更换 `base_url` + `api_key` + `model`。

---

## AIP-001：数据库模型 + 迁移 + 加密（P0）

- **估计耗时**: 60 分钟

### 1.1 新增 `app/core/encryption.py` (~80行)

Fernet 对称加密 API Key：

```python
from cryptography.fernet import Fernet

def get_encryption_key() -> bytes:
    """从 env AI_CONFIG_ENCRY_KEY 获取，未设置则自动生成+WARNING"""

def encrypt_key(plaintext: str) -> str:
    """返回 base64 密文"""

def decrypt_key(ciphertext: str) -> str:
    """解密还原明文"""
```

### 1.2 新增 ORM 模型到 `app/db/models.py`

```python
class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"
    id: Mapped[str]                    # UUID
    name: Mapped[str]                  # 唯一显示名
    provider_type: Mapped[str]         # openai/deepseek/groq/ollama/custom
    api_base_url: Mapped[str | None]   # 空=OpenAI默认
    api_key_encrypted: Mapped[str | None]  # Fernet加密
    model: Mapped[str]                 # gpt-5.4-mini / deepseek-chat
    priority: Mapped[int]              # 越小越高
    is_enabled: Mapped[bool]           # 启用开关
    timeout_seconds: Mapped[int]       # 超时
    use_responses_api: Mapped[bool]    # True=responses.create (仅OpenAI)
    metadata_json: Mapped[dict | None] # 扩展: max_tokens, temperature
    created_at, updated_at

class AccountAIProviderOverride(Base):
    __tablename__ = "account_ai_provider_overrides"
    id: Mapped[str]
    account_id: Mapped[str]            # 唯一
    provider_config_id: Mapped[str]    # FK → ai_provider_configs
    is_active: Mapped[bool]
    created_at, updated_at
```

### 1.3 新增 Alembic 迁移 `alembic/versions/0071_ai_provider_configs.py`

- 创建两张表 + 索引 + 唯一约束
- revision = "0071", down_revision = "0070"

### 1.4 修改 `app/core/settings.py`

新增 3 个字段：
```python
ai_config_encryption_key: str = Field(default="", alias="AI_CONFIG_ENCRY_KEY")
ai_config_cache_ttl_seconds: int = Field(default=60, alias="AI_CONFIG_CACHE_TTL_SECONDS")
ai_config_db_enabled: bool = Field(default=True, alias="AI_CONFIG_DB_ENABLED")
```

### 1.5 修改 `pyproject.toml`

添加依赖: `"cryptography>=44.0,<45.0"`

### 1.6 新增 `app/schemas/ai_providers.py` (~100行)

Pydantic 模型：
- `AIProviderConfigResponse` — 含 `has_api_key: bool`（不暴露密钥）
- `CreateAIProviderConfigRequest` — api_key 明文传入，服务端加密
- `UpdateAIProviderConfigRequest` — 所有字段可选，api_key 不传则保留原密钥
- `TestConnectionRequest` — config_id 或临时配置
- `TestConnectionResponse` — `{status: "ok"|"error", latency_ms, model_echoed, error_type, message}`
- `ReorderRequest` — `{ordered_ids: list[str]}`
- `AccountOverrideResponse`

### 验收标准

1. `alembic upgrade head` 成功
2. 两张表在 PostgreSQL 中存在
3. `encrypt_key` + `decrypt_key` 往返正确
4. `npm run build` 不受影响
5. 现有测试不退化

---

## AIP-002：Service 层 + 缓存 + 通用 Provider（P0）

- **估计耗时**: 90 分钟

### 2.1 新增 `app/providers/ai/generic_provider.py` (~90行)

```python
class GenericOpenAICompatibleProvider(AIProvider):
    """支持所有 OpenAI SDK 兼容 API"""
    provider_name = "generic"

    def __init__(self, display_name, model, api_key, base_url, timeout_seconds, use_responses_api=False):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
        self._use_responses_api = use_responses_api

    async def generate_reply(self, request: AIReplyRequest) -> str:
        if self._use_responses_api:
            # OpenAI responses.create() (同 OpenAIProvider)
        else:
            # chat.completions.create() (同 DeepSeekProvider)
```

### 2.2 新增 `app/services/ai_provider_cache.py` (~100行)

```python
class AIProviderCache:
    _lock: threading.Lock
    _chain: list[AIProviderConfig] | None
    _overrides: dict[str, str] | None
    _loaded_at: float

    def get_active_chain(self, session) -> list[AIProviderConfig]
    def get_account_override(self, session, account_id) -> AIProviderConfig | None
    def invalidate(self) -> None
```

TTL 60s，CRUD 后显式 `invalidate()`。

### 2.3 新增 `app/services/ai_provider_config_service.py` (~220行)

```python
class AIProviderConfigService:
    def __init__(self, session: Session)

    # CRUD
    async def list_configs(self, include_disabled=False) -> list[AIProviderConfig]
    async def get_config(self, config_id) -> AIProviderConfig
    async def create_config(self, data: CreateRequest) -> AIProviderConfig  # 加密 api_key
    async def update_config(self, config_id, data: UpdateRequest) -> AIProviderConfig
    async def delete_config(self, config_id) -> None  # 级联删除 override
    async def reorder_configs(self, ordered_ids) -> None

    # Account overrides
    async def get_account_override(self, account_id) -> AIProviderConfig | None
    async def set_account_override(self, account_id, config_id) -> None
    async def clear_account_override(self, account_id) -> None

    # Test connection
    async def test_connection(self, request: TestConnectionRequest) -> TestConnectionResponse

    # Seed from .env
    async def seed_from_env(self, settings) -> int  # 返回新增数
```

**test_connection 实现**:
1. 用配置参数实例化 `AsyncOpenAI`
2. 发送 `chat.completions.create(model=..., messages=[{"role":"user","content":"Hi"}], max_tokens=5)`
3. 成功: `{status: "ok", latency_ms: 230, model_echoed: "deepseek-chat"}`
4. 失败: `{status: "error", error_type: "auth_failed"|"timeout"|"model_not_found", message: "..."}`

**seed_from_env 实现**:
1. 检查 `ai_provider_configs` 表是否为空
2. 如果空 + `settings.openai_api_key` 存在 → INSERT OpenAI 配置 (priority=0)
3. 如果空 + `settings.deepseek_api_key` 存在 → INSERT DeepSeek 配置 (priority=10)
4. 已有数据则跳过

### 验收标准

1. `GenericOpenAICompatibleProvider` 可实例化
2. 缓存 TTL 生效
3. CRUD 操作后缓存自动失效
4. seed_from_env 正确种子
5. 现有测试不退化

---

## AIP-003：工厂函数重构 + API 路由（P0）

- **估计耗时**: 90 分钟

### 3.1 重构 `app/providers/factory.py` 的 `get_ai_provider()`

```python
def get_ai_provider(settings: Settings, account_id: str | None = None) -> AIProvider:
    """
    优先级:
    1. test_mode → MockAIProvider
    2. DB 有数据 → 检查 account_id 覆盖 → 构建 FallbackAIProvider 链
    3. DB 无数据 → 回退 .env 配置（现有逻辑）
    4. 最终兜底 → MockAIProvider
    """
```

**向后兼容**: DB 为空时完全走旧路径，行为与改动前一致。

### 3.2 修改调用方

- `app/services/ai_queue_processor.py` — 传 `account_id` 给 `get_ai_provider(settings, account_id=...)`
- `app/services/chat.py` — 同上

先用 Grep 确认这两处调用 `get_ai_provider` 的确切位置。

### 3.3 新增 `app/api/routes/ai_providers.py` (~200行)

11 个端点：

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/api/ai-providers` | SETTINGS_READ |
| POST | `/api/ai-providers` | SETTINGS_MANAGE |
| GET | `/api/ai-providers/{config_id}` | SETTINGS_READ |
| PATCH | `/api/ai-providers/{config_id}` | SETTINGS_MANAGE |
| DELETE | `/api/ai-providers/{config_id}` | SETTINGS_MANAGE |
| POST | `/api/ai-providers/{config_id}/test` | SETTINGS_MANAGE |
| PUT | `/api/ai-providers/reorder` | SETTINGS_MANAGE |
| GET | `/api/ai-providers/account-overrides` | SETTINGS_READ |
| PUT | `/api/ai-providers/account-overrides/{account_id}` | SETTINGS_MANAGE |
| DELETE | `/api/ai-providers/account-overrides/{account_id}` | SETTINGS_MANAGE |

权限使用已有的 `Permission.SETTINGS_READ` 和 `Permission.SETTINGS_MANAGE`。

### 3.4 修改 `app/api/deps.py`

添加依赖注入：
```python
def get_ai_provider_config_service(session=Depends(get_db_session)) -> AIProviderConfigService
```

### 3.5 修改 `app/main.py`

1. 注册路由: `app.include_router(ai_providers_router)`
2. lifespan 中添加种子逻辑:
```python
if settings.ai_config_db_enabled:
    session = get_sessionmaker()()
    service = AIProviderConfigService(session)
    seeded = service.seed_from_env(settings)
    if seeded > 0: logger.info("seeded_ai_provider_configs", count=seeded)
    session.close()
```

### 验收标准

1. 所有 11 个端点可调用
2. GET 列表返回脱敏数据（`has_api_key: true`，不暴露密钥）
3. 工厂函数: DB 有数据时用 DB，DB 空时用 .env
4. `account_id` 覆盖正确
5. 现有测试不退化

---

## AIP-004：测试（P0）

- **估计耗时**: 60 分钟

### 4.1 新增 `tests/test_ai_provider_config.py` (~200行, 9 用例)

1. test_create_config_stores_encrypted_key
2. test_list_configs_hides_api_key
3. test_update_config_preserves_key_on_empty
4. test_reorder_updates_priorities
5. test_delete_config_cascades_overrides
6. test_seed_from_env_creates_records
7. test_seed_skips_when_already_populated
8. test_account_override_crud
9. test_cache_invalidation_on_crud

### 4.2 新增 `tests/test_ai_provider_factory.py` (~150行, 7 用例)

1. test_factory_uses_db_configs_when_available
2. test_factory_falls_back_to_env_when_db_empty
3. test_factory_account_override_takes_priority
4. test_factory_respects_enabled_flag
5. test_factory_respects_priority_order
6. test_factory_always_includes_mock_fallback
7. test_factory_test_mode_returns_mock

### 4.3 新增 `tests/test_ai_provider_api.py` (~150行, 8 用例)

1. test_api_create_provider
2. test_api_list_providers_masks_keys
3. test_api_update_provider
4. test_api_delete_provider
5. test_api_reorder_providers
6. test_api_test_connection
7. test_api_requires_settings_manage_permission
8. test_api_account_override_lifecycle

### 验收标准

1. 24+ 测试全部通过
2. 现有测试不退化

---

## AIP-005：全量验证（P0）

- **估计耗时**: 15 分钟

```powershell
cd E:\codex\WhatsApp

# 新测试
.venv\Scripts\python.exe -m pytest tests/test_ai_provider_config.py tests/test_ai_provider_factory.py tests/test_ai_provider_api.py -q -x

# 现有测试
.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_log_sanitization.py -q

# Docker 重建
docker compose up -d app
# 等待 15 秒
# 验证端点
Invoke-WebRequest -Uri "http://localhost:8000/api/ai-providers" -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"} -UseBasicParsing
```

### 最终验收清单

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | 新测试 | 24+ 通过 |
| 2 | 现有测试 | 不退化 |
| 3 | GET /api/ai-providers | 200 + 脱敏 |
| 4 | POST /api/ai-providers | 200 + 加密存储 |
| 5 | POST test-connection | 200 + latency |
| 6 | Docker 重启后配置保留 | DB 持久化 |
| 7 | 工厂函数向后兼容 | DB 空时走 .env |

---

## 全局约束

1. **不碰前端代码**
2. **不碰 H5 相关**
3. **所有新代码有类型注解 + 异步 I/O**
4. **API Key 在 DB 中加密，API 响应不暴露**
5. **工厂函数向后兼容**: DB 空时完全走旧路径
6. **现有 `OpenAIProvider` 和 `DeepSeekProvider` 保留不动**
7. **进度文件**: `.codex-run/progress/AIP-XXX.json`
8. **一次性执行全部任务，不中途暂停**

---

## 新增文件清单

| 文件 | 行数 |
|------|------|
| `app/core/encryption.py` | ~80 |
| `app/schemas/ai_providers.py` | ~100 |
| `app/services/ai_provider_config_service.py` | ~220 |
| `app/services/ai_provider_cache.py` | ~100 |
| `app/providers/ai/generic_provider.py` | ~90 |
| `app/api/routes/ai_providers.py` | ~200 |
| `alembic/versions/0071_ai_provider_configs.py` | ~80 |
| `tests/test_ai_provider_config.py` | ~200 |
| `tests/test_ai_provider_factory.py` | ~150 |
| `tests/test_ai_provider_api.py` | ~150 |
| **总计** | **~1370** |

## 修改文件清单

| 文件 | 改动 |
|------|------|
| `app/db/models.py` | +35行 (2 模型) |
| `app/core/settings.py` | +5行 |
| `app/providers/factory.py` | ~40行重写 |
| `app/api/deps.py` | +10行 |
| `app/main.py` | +10行 |
| `app/services/ai_queue_processor.py` | 1行 |
| `app/services/chat.py` | 1行 |
| `pyproject.toml` | +1行 |
