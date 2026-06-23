"""Initialize the fixed default H5 template record."""

import sys

from app.db.session import get_sessionmaker
from app.services.h5_template_bootstrap_service import H5TemplateBootstrapService


def run() -> None:
    """Ensure the fixed default template exists and is normalized."""
    session = get_sessionmaker()()
    try:
        created = H5TemplateBootstrapService(session).ensure_default_template()
        if created:
            print("[OK] Fixed default H5 template created.")
        else:
            print("[SKIP] Fixed default H5 template already exists.")
    except Exception as exc:
        session.rollback()
        print(f"[ERROR] Failed to create default template: {exc}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    run()
