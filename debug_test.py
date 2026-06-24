"""Debug: Check tests."""
import os
os.environ["AI_CONFIG_DB_ENABLED"] = "false"
os.environ["TEST_MODE"] = "false"
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

from app.core.settings import Settings
s = Settings(test_mode=False, ai_provider="openai")
print(f"openai_api_key={s.openai_api_key!r}")
print(f"deepseek_api_key={s.deepseek_api_key!r}")
print(f"ai_config_db_enabled={s.ai_config_db_enabled!r}")

from app.providers.factory import get_ai_provider
from app.providers.ai.mock_provider import MockAIProvider
p = get_ai_provider(s)
print(f"provider type: {type(p).__name__}")
print(f"is MockAIProvider: {isinstance(p, MockAIProvider)}")
