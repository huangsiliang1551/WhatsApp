import json
import re
from pathlib import Path

from app.core import metrics as app_metrics
from app.core.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_covers_all_runtime_settings_aliases() -> None:
    env_example = ROOT / ".env.example"
    configured_keys = {
        line.split("=", 1)[0]
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    settings_aliases = {
        str(field.alias)
        for field in Settings.model_fields.values()
        if field.alias is not None
    }

    assert settings_aliases <= configured_keys


def test_meta_webhook_subscribed_fields_defaults_cover_management_events() -> None:
    env_example = ROOT / ".env.example"
    configured = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    required_fields = {
        "messages",
        "message_template_status_update",
        "message_template_quality_update",
        "phone_number_quality_update",
        "phone_number_name_update",
        "phone_number_status_update",
    }
    settings_fields = set(Settings().meta_webhook_subscribed_fields.split(","))
    env_fields = set(configured["META_WEBHOOK_SUBSCRIBED_FIELDS"].split(","))

    assert required_fields <= settings_fields
    assert settings_fields == env_fields


def test_docker_compose_bind_mount_sources_exist() -> None:
    compose_file = ROOT / "docker-compose.yml"
    compose_text = compose_file.read_text(encoding="utf-8")
    bind_sources = re.findall(r"-\s+\./([^:\r\n]+):", compose_text)

    assert bind_sources
    for source in bind_sources:
        assert (ROOT / source).exists(), f"Missing compose bind source: {source}"


def test_docker_compose_uses_valid_alembic_startup_command() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    prod_compose_text = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    app_block_match = re.search(r"app:\s*(.*?)(?:\n\s{2}\w|\nvolumes:)", compose_text, re.DOTALL)
    prod_app_block_match = re.search(r"app:\s*(.*?)(?:\n\s{2}\w|\nvolumes:)", prod_compose_text, re.DOTALL)

    assert app_block_match is not None
    assert prod_app_block_match is not None

    app_block = app_block_match.group(1)
    prod_app_block = prod_app_block_match.group(1)

    assert "python -m alembic" not in app_block
    assert "python -m alembic" not in prod_app_block
    assert 'command: sh -c "alembic upgrade heads &&' in app_block
    assert 'command: sh -c "alembic upgrade heads &&' in prod_app_block
    assert re.search(r"worker:.*?command:\s+sh -c \"python -m app\.worker\"", compose_text, re.DOTALL)


def test_docker_compose_sets_container_queue_redis_url_explicitly() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    app_block_match = re.search(r"app:\s*(.*?)(?:\n\s{2}\w|\nvolumes:)", compose_text, re.DOTALL)
    worker_block_match = re.search(r"worker:\s*(.*?)(?:\n\s{2}\w|\nvolumes:)", compose_text, re.DOTALL)

    assert app_block_match is not None
    assert worker_block_match is not None

    app_block = app_block_match.group(1)
    worker_block = worker_block_match.group(1)

    assert "QUEUE_REDIS_URL: redis://redis:6379/1" in app_block
    assert "QUEUE_REDIS_URL: redis://redis:6379/1" in worker_block
    assert "QUEUE_REDIS_URL: redis://localhost:6379/1" not in app_block
    assert "QUEUE_REDIS_URL: redis://localhost:6379/1" not in worker_block


def test_docker_compose_includes_alertmanager_monitoring_stack() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "alertmanager:" in compose_text
    assert "./monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro" in compose_text
    assert 'image: prom/alertmanager:v0.28.1' in compose_text
    assert '"9093:9093"' in compose_text


def test_prometheus_config_wires_alertmanager_target() -> None:
    prometheus_text = (ROOT / "monitoring" / "prometheus" / "prometheus.yml").read_text(
        encoding="utf-8"
    )

    assert "alerting:" in prometheus_text
    assert "alertmanagers:" in prometheus_text
    assert "alertmanager:9093" in prometheus_text


def test_alertmanager_config_has_default_receiver_route() -> None:
    alertmanager_text = (
        ROOT / "monitoring" / "alertmanager" / "alertmanager.yml"
    ).read_text(encoding="utf-8")

    assert "route:" in alertmanager_text
    assert "receiver: default-null" in alertmanager_text
    assert "receivers:" in alertmanager_text
    assert "name: default-null" in alertmanager_text


def test_verify_ci_script_prefers_workspace_venv_and_checks_command_failures() -> None:
    script_text = (ROOT / "scripts" / "verify-ci.ps1").read_text(encoding="utf-8")

    assert ".venv\\Scripts\\python.exe" in script_text
    assert "[1/6] Running backend tests..." in script_text
    assert "[2/6] Building frontend..." in script_text
    assert "[3/6] Validating Docker Compose..." in script_text
    assert "function Invoke-CheckedCommand" in script_text
    assert 'Invoke-CheckedCommand -FilePath $pythonCommand -Arguments @("-m", "pytest")' in script_text
    assert 'Invoke-CheckedCommand -FilePath "npm" -Arguments @("run", "build")' in script_text
    assert "docker compose config" in script_text
    assert "prom/alertmanager:v0.28.1" in script_text
    assert "amtool" in script_text
    assert "check-config" in script_text
    assert "failed with exit code" in script_text


def test_launch_readiness_script_checks_provider_status_buffer_signal() -> None:
    script_text = (ROOT / "scripts" / "check-launch-readiness.ps1").read_text(encoding="utf-8")

    assert "[1/5] Checking health endpoint..." in script_text
    assert "[2/5] Checking launch readiness endpoint..." in script_text
    assert "[3/5] Checking provider status buffer endpoint..." in script_text
    assert "[4/5] Checking metrics summary endpoint..." in script_text
    assert "[5/5] Checking Alertmanager readiness endpoint..." in script_text
    assert "/api/runtime/provider-status-buffer?limit=1" in script_text
    assert "Provider status buffer pending" in script_text
    assert "pending_count" in script_text
    assert "replayed_count" in script_text
    assert "oldest_pending_event" in script_text
    assert "pending_accounts_ranked" in script_text
    assert "Oldest pending provider status event" in script_text
    assert "Pending provider status accounts" in script_text
    assert "Provider status buffer still contains" in script_text
    assert "[string]$AlertmanagerUrl = \"http://127.0.0.1:9093\"" in script_text
    assert '"$AlertmanagerUrl/-/ready"' in script_text
    assert "Alertmanager responded from" in script_text


def test_recovery_runbook_reuses_launch_readiness_validation_after_restore() -> None:
    runbook_text = (ROOT / "docs" / "recovery-runbook.md").read_text(encoding="utf-8")

    assert "Invoke-WebRequest http://127.0.0.1:8000/api/runtime/launch-readiness" in runbook_text
    assert "Invoke-WebRequest http://127.0.0.1:8000/api/runtime/provider-status-buffer?limit=20" in runbook_text
    assert ".\\scripts\\check-launch-readiness.ps1 -ShowChecks" in runbook_text


def test_deployment_checklist_covers_scoped_launch_readiness_and_recovery_gate() -> None:
    checklist_text = (ROOT / "docs" / "deployment-checklist.md").read_text(encoding="utf-8")

    assert ".\\scripts\\verify-ci.ps1" in checklist_text
    assert ".\\scripts\\check-launch-readiness.ps1" in checklist_text
    assert ".\\scripts\\check-launch-readiness.ps1 -AccountId demo-account-cn -ShowChecks" in checklist_text
    assert ".\\scripts\\check-launch-readiness.ps1 -FailOnWarnings" in checklist_text
    assert "Invoke-WebRequest http://127.0.0.1:8000/api/runtime/launch-readiness" in checklist_text
    assert (
        'Invoke-WebRequest "http://127.0.0.1:8000/api/runtime/launch-readiness?account_id=demo-account-cn"'
        in checklist_text
    )
    assert "Invoke-WebRequest http://127.0.0.1:8000/api/runtime/provider-status-buffer?limit=20" in checklist_text
    assert "Invoke-WebRequest http://127.0.0.1:9093/-/ready" in checklist_text
    assert "blocker_count = 0" in checklist_text
    assert "recovery-runbook.md" in checklist_text


def test_prometheus_alerts_and_grafana_dashboard_reference_existing_metrics() -> None:
    known_metrics = _collect_exported_metric_names()
    referenced_metrics = set()

    alerts_file = ROOT / "monitoring" / "prometheus" / "alerts.yml"
    for expression in re.findall(r"^\s*expr:\s*(.+)$", alerts_file.read_text(encoding="utf-8"), re.MULTILINE):
        referenced_metrics.update(_extract_metric_names(expression))

    dashboard_file = (
        ROOT / "monitoring" / "grafana" / "dashboards" / "whatsapp-platform-overview.json"
    )
    dashboard = json.loads(dashboard_file.read_text(encoding="utf-8"))
    for expression in _iter_dashboard_expressions(dashboard):
        referenced_metrics.update(_extract_metric_names(expression))

    assert referenced_metrics <= known_metrics


def _collect_exported_metric_names() -> set[str]:
    metric_objects = (
        app_metrics.mock_inbound_messages_total,
        app_metrics.business_inbound_messages_total,
        app_metrics.whatsapp_webhook_messages_total,
        app_metrics.whatsapp_webhook_status_updates_total,
        app_metrics.whatsapp_webhook_signature_failures_total,
        app_metrics.whatsapp_webhook_messages_scoped_total,
        app_metrics.whatsapp_webhook_status_updates_scoped_total,
        app_metrics.whatsapp_webhook_template_updates_total,
        app_metrics.whatsapp_webhook_phone_number_updates_total,
        app_metrics.whatsapp_webhook_signature_failures_scoped_total,
        app_metrics.whatsapp_webhook_phone_scope_rejections_total,
        app_metrics.message_processing_failures_total,
        app_metrics.business_outbound_messages_total,
        app_metrics.business_ai_replies_total,
        app_metrics.business_template_sends_total,
        app_metrics.business_template_send_failures_total,
        app_metrics.message_delivery_events_total,
        app_metrics.provider_status_event_buffer_pending_current,
        app_metrics.provider_status_event_buffer_oldest_age_seconds,
        app_metrics.provider_status_event_buffer_events_total,
        app_metrics.translation_operations_total,
        app_metrics.queue_jobs_total,
        app_metrics.queue_jobs_current,
        app_metrics.task_submissions_total,
        app_metrics.task_reviews_total,
        app_metrics.tickets_created_total,
        app_metrics.tickets_status_transition_total,
    )
    names = {"up"}
    for metric in metric_objects:
        for collected in metric.collect():
            names.add(collected.name)
            names.add(f"{collected.name}_total")
            names.add(f"{collected.name}_created")
            names.update(sample.name for sample in collected.samples)
    return names


def _iter_dashboard_expressions(value: object) -> list[str]:
    if isinstance(value, dict):
        expressions: list[str] = []
        for key, item in value.items():
            if key == "expr" and isinstance(item, str):
                expressions.append(item)
            else:
                expressions.extend(_iter_dashboard_expressions(item))
        return expressions
    if isinstance(value, list):
        expressions = []
        for item in value:
            expressions.extend(_iter_dashboard_expressions(item))
        return expressions
    return []


def _extract_metric_names(expression: str) -> set[str]:
    expression_without_strings = re.sub(r'"[^"]*"', '""', expression)
    return set(re.findall(r"([a-zA-Z_:][a-zA-Z0-9_:]*)\s*(?=\{|\[)", expression_without_strings))
