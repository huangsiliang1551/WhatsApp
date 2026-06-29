from __future__ import annotations

import json

from app.core.production_guard import collect_production_issues
from app.core.settings import get_settings


def main() -> int:
    settings = get_settings()
    issues = collect_production_issues(settings)
    blocking = [issue for issue in issues if issue.severity == "S"]
    advisory = [issue for issue in issues if issue.severity != "S"]
    payload = {
        "ok": not blocking,
        "app_env": getattr(settings, "app_env", ""),
        "test_mode": bool(getattr(settings, "test_mode", False)),
        "issue_count": len(issues),
        "blocking_issue_count": len(blocking),
        "advisory_issue_count": len(advisory),
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
            }
            for issue in issues
        ],
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not blocking else 1


if __name__ == "__main__":
    raise SystemExit(main())
