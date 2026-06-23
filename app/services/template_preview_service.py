"""Template preview service — IV-BE-005.

Provides system variable definitions and variable substitution
for message template preview.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════
# System variables — available in all templates
# ═══════════════════════════════════════════════════════════════════════════
SYSTEM_VARIABLES: dict[str, str] = {
    "{{customer_name}}": "客户姓名",
    "{{customer_phone}}": "客户手机号",
    "{{recharge_total}}": "累计充值金额",
    "{{withdraw_total}}": "累计提现金额",
    "{{brand_name}}": "品牌名称",
    "{{current_date}}": "当前日期",
    "{{current_time}}": "当前时间",
    "{{agent_name}}": "客服名称",
    "{{order_id}}": "订单编号",
    "{{product_name}}": "商品名称",
}

# ═══════════════════════════════════════════════════════════════════════════
# Mock data for preview
# ═══════════════════════════════════════════════════════════════════════════
MOCK_VARIABLES: dict[str, str] = {
    "{{customer_name}}": "张三",
    "{{customer_phone}}": "138****8888",
    "{{recharge_total}}": "¥1,234.56",
    "{{withdraw_total}}": "¥500.00",
    "{{brand_name}}": "示例品牌",
    "{{current_date}}": datetime.now().strftime("%Y-%m-%d"),
    "{{current_time}}": datetime.now().strftime("%H:%M"),
    "{{agent_name}}": "客服小美",
    "{{order_id}}": "ORD-20260619-0001",
    "{{product_name}}": "示例商品",
}


class TemplatePreviewService:
    """Template variable preview and substitution."""

    def get_variables(self) -> list[dict[str, str]]:
        """Return system variable definitions."""
        return [
            {"code": code, "label": label}
            for code, label in SYSTEM_VARIABLES.items()
        ]

    def preview(
        self,
        template_content: str,
        variables: dict[str, str],
    ) -> str:
        """Replace variables with provided values."""
        result = template_content
        for key, value in variables.items():
            result = result.replace(key, value)
        return result

    def preview_with_mock(self, template_content: str) -> str:
        """Replace variables with mock data for preview."""
        return self.preview(template_content, MOCK_VARIABLES)

    def extract_variables(self, template_content: str) -> list[str]:
        """Extract all {{variable}} placeholders from content."""
        import re

        return re.findall(r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}", template_content)
