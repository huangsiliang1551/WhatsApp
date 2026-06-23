from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="WhatsApp Support Platform", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    test_mode: bool = Field(default=False, alias="TEST_MODE")
    auth_required: bool = Field(default=True, alias="AUTH_REQUIRED")
    h5_member_session_cookie_name: str = Field(
        default="h5_member_session",
        alias="H5_MEMBER_SESSION_COOKIE_NAME",
    )
    h5_member_refresh_cookie_name: str = Field(
        default="h5_member_refresh",
        alias="H5_MEMBER_REFRESH_COOKIE_NAME",
    )
    h5_member_session_ttl_hours: int = Field(default=12, alias="H5_MEMBER_SESSION_TTL_HOURS")
    h5_member_refresh_ttl_days: int = Field(default=30, alias="H5_MEMBER_REFRESH_TTL_DAYS")
    h5_member_cookie_secure: bool = Field(default=False, alias="H5_MEMBER_COOKIE_SECURE")
    h5_member_cookie_domain: str = Field(default="", alias="H5_MEMBER_COOKIE_DOMAIN")
    h5_member_cookie_samesite: str = Field(default="lax", alias="H5_MEMBER_COOKIE_SAMESITE")
    h5_member_max_sessions_per_user: int = Field(default=5, alias="H5_MEMBER_MAX_SESSIONS_PER_USER")
    h5_member_login_lockout_threshold: int = Field(default=5, alias="H5_MEMBER_LOGIN_LOCKOUT_THRESHOLD")
    h5_member_login_lockout_minutes: int = Field(default=15, alias="H5_MEMBER_LOGIN_LOCKOUT_MINUTES")
    h5_member_order_cache_ttl_seconds: int = Field(default=300, alias="H5_MEMBER_ORDER_CACHE_TTL_SECONDS")
    h5_member_logistics_cache_ttl_seconds: int = Field(default=600, alias="H5_MEMBER_LOGISTICS_CACHE_TTL_SECONDS")

    database_url: str = Field(default="postgresql://whatsapp_user:secure_password@localhost:5432/whatsapp_bot", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    queue_redis_url: str = Field(default="redis://localhost:6379/1", alias="QUEUE_REDIS_URL")
    queue_provider: str = Field(default="redis", alias="QUEUE_PROVIDER")
    queue_default_timeout_seconds: int = Field(default=30, alias="QUEUE_DEFAULT_TIMEOUT")
    queue_max_retries: int = Field(default=3, alias="QUEUE_MAX_RETRIES")
    queue_poll_timeout_seconds: int = Field(default=5, alias="QUEUE_POLL_TIMEOUT_SECONDS")
    sleeping_scan_interval_seconds: int = Field(default=900, alias="SLEEPING_SCAN_INTERVAL_SECONDS")
    sleeping_threshold_hours: int = Field(default=48, alias="SLEEPING_THRESHOLD_HOURS")
    media_storage_root: str = Field(default="storage/media-assets", alias="MEDIA_STORAGE_ROOT")
    task_proof_storage_root: str = Field(default="storage/task-proofs", alias="TASK_PROOF_STORAGE_ROOT")

    ai_provider: str = Field(default="openai", alias="AI_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4-mini", alias="OPENAI_MODEL")

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_api_base: str = Field(default="https://api.deepseek.com/v1", alias="DEEPSEEK_API_BASE")
    messaging_provider: str = Field(default="mock", alias="MESSAGING_PROVIDER")
    meta_management_provider: str = Field(default="", alias="META_MANAGEMENT_PROVIDER")
    meta_app_id: str = Field(default="", alias="META_APP_ID")
    meta_app_secret: str = Field(default="", alias="META_APP_SECRET")
    meta_graph_api_base: str = Field(default="https://graph.facebook.com", alias="META_GRAPH_API_BASE")
    meta_graph_api_version: str = Field(default="v20.0", alias="META_GRAPH_API_VERSION")
    meta_webhook_subscribed_fields: str = Field(
        default=(
            "messages,message_template_status_update,message_template_quality_update,"
            "phone_number_quality_update,phone_number_name_update,phone_number_status_update"
        ),
        alias="META_WEBHOOK_SUBSCRIBED_FIELDS",
    )
    template_registry_provider: str = Field(default="", alias="TEMPLATE_REGISTRY_PROVIDER")
    messaging_request_timeout_seconds: int = Field(default=30, alias="MESSAGING_REQUEST_TIMEOUT_SECONDS")
    # Legacy single-account fallback; formal rollout should use persisted Meta account records.
    wa_phone_id: str = Field(default="", alias="WA_PHONE_ID")
    wa_access_token: str = Field(default="", alias="WA_ACCESS_TOKEN")
    wa_verify_token: str = Field(default="", alias="WA_VERIFY_TOKEN")
    wa_app_secret: str = Field(default="", alias="WA_APP_SECRET")
    wa_business_account_id: str = Field(default="", alias="WA_BUSINESS_ACCOUNT_ID")
    ecommerce_provider: str = Field(default="mock", alias="ECOMMERCE_PROVIDER")
    ecommerce_request_timeout_seconds: int = Field(default=15, alias="ECOMMERCE_REQUEST_TIMEOUT_SECONDS")
    translation_provider: str = Field(default="", alias="TRANSLATION_PROVIDER")
    live_translation_enabled: bool = Field(default=True, alias="LIVE_TRANSLATION_ENABLED")
    console_language: str = Field(default="zh-CN", alias="CONSOLE_LANGUAGE")
    auto_translate_on_human_handover: bool = Field(default=False, alias="AUTO_TRANSLATE_ON_HUMAN_HANDOVER")
    auto_translate_on_conversation_open: bool = Field(default=False, alias="AUTO_TRANSLATE_ON_CONVERSATION_OPEN")
    auto_translate_operator_outbound: bool = Field(default=True, alias="AUTO_TRANSLATE_OPERATOR_OUTBOUND")
    llm_request_timeout_seconds: int = Field(default=30, alias="LLM_REQUEST_TIMEOUT_SECONDS")

    # AI quality check settings
    ai_quality_check_enabled: bool = Field(default=True, alias="AI_QUALITY_CHECK_ENABLED")
    ai_quality_reject_threshold: float = Field(default=0.3, alias="AI_QUALITY_REJECT_THRESHOLD")

    # AI context window settings
    ai_context_max_messages: int = Field(default=10, alias="AI_CONTEXT_MAX_MESSAGES")
    ai_context_max_history_chars: int = Field(default=2000, alias="AI_CONTEXT_MAX_HISTORY_CHARS")
    ai_context_max_message_chars: int = Field(default=500, alias="AI_CONTEXT_MAX_MESSAGE_CHARS")
    ai_context_max_total_chars: int = Field(default=4000, alias="AI_CONTEXT_MAX_TOTAL_CHARS")

    # AI provider config DB encryption & cache
    ai_config_encryption_key: str = Field(default="", alias="AI_CONFIG_ENCRY_KEY")
    ai_config_cache_ttl_seconds: int = Field(default=60, alias="AI_CONFIG_CACHE_TTL_SECONDS")
    ai_config_db_enabled: bool = Field(default=True, alias="AI_CONFIG_DB_ENABLED")

    # Admin JWT authentication
    admin_jwt_secret: str = Field(default="change-me-in-production", alias="ADMIN_JWT_SECRET")
    admin_access_token_ttl_minutes: int = Field(default=120, alias="ADMIN_ACCESS_TOKEN_TTL_MINUTES")
    admin_refresh_token_ttl_days: int = Field(default=7, alias="ADMIN_REFRESH_TOKEN_TTL_DAYS")
    admin_default_username: str = Field(default="admin", alias="ADMIN_DEFAULT_USERNAME")
    admin_default_password: str = Field(default="admin123", alias="ADMIN_DEFAULT_PASSWORD")

    # Health check
    health_check_interval_minutes: int = Field(default=60, alias="HEALTH_CHECK_INTERVAL_MINUTES")

    # Database backups
    backup_dir: str = Field(default="/opt/whatsapp/backups", alias="BACKUP_DIR")

    # CORS
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000", alias="CORS_ORIGINS")

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")

    # Database connection pool
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")

    # Uvicorn workers (only used in production entrypoint)
    uvicorn_workers: int = Field(default=4, alias="UVICORN_WORKERS")

    # Webhook
    webhook_signature_enabled: bool = Field(default=True, alias="WEBHOOK_SIGNATURE_ENABLED")

    # Global webhook defaults (used when per-account config is not set)
    meta_global_webhook_callback_url: str = Field(default="", alias="META_GLOBAL_WEBHOOK_CALLBACK_URL")
    meta_global_webhook_verify_token: str = Field(default="", alias="META_GLOBAL_WEBHOOK_VERIFY_TOKEN")

    # SLA thresholds
    sla_warning_seconds: int = Field(default=300, alias="SLA_WARNING_SECONDS")
    sla_critical_seconds: int = Field(default=600, alias="SLA_CRITICAL_SECONDS")

    def resolve_translation_provider_name(self) -> str:
        if not self.live_translation_enabled:
            return "disabled"

        explicit_provider = (self.translation_provider or "").strip().lower()
        if explicit_provider:
            return explicit_provider

        ai_provider = (self.ai_provider or "").strip().lower()
        if ai_provider:
            return ai_provider

        return "fallback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
