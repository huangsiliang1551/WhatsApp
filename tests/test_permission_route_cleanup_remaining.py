from pathlib import Path


REMAINING_ROUTE_FILES = [
    "app/api/routes/agency_billing.py",
    "app/api/routes/agents.py",
    "app/api/routes/api_stats.py",
    "app/api/routes/backups.py",
    "app/api/routes/batch.py",
    "app/api/routes/customer_profile.py",
    "app/api/routes/deploy_history.py",
    "app/api/routes/dev.py",
    "app/api/routes/domain_verification.py",
    "app/api/routes/ecommerce.py",
    "app/api/routes/h5_languages.py",
    "app/api/routes/h5_translations.py",
    "app/api/routes/marketing_stats.py",
    "app/api/routes/media_assets.py",
    "app/api/routes/metrics.py",
    "app/api/routes/notifications.py",
    "app/api/routes/operations.py",
    "app/api/routes/performance.py",
    "app/api/routes/platform.py",
    "app/api/routes/platform_member_verifications.py",
    "app/api/routes/platform_member_whatsapp_bindings.py",
    "app/api/routes/platform_withdrawals.py",
    "app/api/routes/product_packages.py",
    "app/api/routes/products.py",
    "app/api/routes/queue.py",
    "app/api/routes/rate_limits.py",
    "app/api/routes/reports.py",
    "app/api/routes/search.py",
    "app/api/routes/sign_in.py",
    "app/api/routes/site_permissions.py",
    "app/api/routes/site_waba.py",
    "app/api/routes/task_instances.py",
    "app/api/routes/translation_providers.py",
    "app/api/routes/waba_assignment.py",
    "app/api/routes/whatsapp_analytics.py",
]


def test_remaining_route_files_no_longer_depend_on_permission_enum() -> None:
    offending: list[str] = []
    for route_path in REMAINING_ROUTE_FILES:
        text = Path(route_path).read_text(encoding="utf-8", errors="ignore")
        if "from app.core.auth import Permission" in text:
            offending.append(f"{route_path}: import")
        if "Permission." in text or 'Permission("' in text:
            offending.append(f"{route_path}: usage")

    assert offending == []
