"""Data migration script for multi-tenant architecture.

Migrates existing data to the multi-tenant structure:
1. Create a default agency for all existing orphan sites
2. Set existing agents with no user_type to super_admin
3. Assign existing WABAs to the default agency
4. Set existing templates/knowledge as global (agency_id = NULL)

Run this once after alembic migrations have been applied.
"""

import sys
from datetime import datetime, timezone
from uuid import uuid4

from app.db.models import (
    Agency,
    Agent,
    AgencyBilling,
    H5Site,
    H5Template,
    SupportKnowledgeEntry,
    WhatsAppBusinessAccount,
)
from app.db.session import get_sessionmaker


DEFAULT_AGENCY_NAME = "Default Agency"
DEFAULT_AGENCY_USERNAME = "default_agency"


def run() -> None:
    """Run the migration."""
    session = get_sessionmaker()()
    try:
        # ─── 1. Create default agency ───────────────────────────────────
        existing = session.query(Agency).filter_by(name=DEFAULT_AGENCY_NAME).first()
        if existing:
            default_agency = existing
            print(f"[OK] Default agency already exists: {default_agency.id}")
        else:
            default_agency = Agency(
                id=str(uuid4()),
                name=DEFAULT_AGENCY_NAME,
                brand_name="Default",
                status="active",
                created_at=datetime.now(timezone.utc),
            )
            session.add(default_agency)
            session.flush()
            print(f"[OK] Created default agency: {default_agency.id}")

        # ─── 2. Set agents user_type ───────────────────────────────────
        agents_without_type = session.query(Agent).filter(
            (Agent.user_type.is_(None)) | (Agent.user_type == "")
        ).all()
        for agent in agents_without_type:
            agent.user_type = "super_admin"
            print(f"  [OK] Set agent {agent.id} -> super_admin")
        if not agents_without_type:
            print("[SKIP] No agents without user_type found")

        # ─── 3. Assign orphan sites to default agency ──────────────────
        orphan_sites = session.query(H5Site).filter(H5Site.agency_id.is_(None)).all()
        for site in orphan_sites:
            site.agency_id = default_agency.id
            print(f"  [OK] Assigned site {site.id} ({site.site_key}) -> default agency")
        if not orphan_sites:
            print("[SKIP] No orphan sites found")

        # ─── 4. Assign orphan WABAs to default agency ──────────────────
        orphan_wabas = session.query(WhatsAppBusinessAccount).filter(
            WhatsAppBusinessAccount.agency_id.is_(None)
        ).all()
        for waba in orphan_wabas:
            waba.agency_id = default_agency.id
            print(f"  [OK] Assigned WABA {waba.id} -> default agency")
        if not orphan_wabas:
            print("[SKIP] No orphan WABAs found")

        # ─── 5. Set orphan templates as global ─────────────────────────
        # H5Template doesn't have agency_id, but AgencyTemplate does
        print("[INFO] H5Templates are global by design (no agency_id field)")

        # ─── 6. Set orphan knowledge entries as global ──────────────────
        orphan_kb = session.query(SupportKnowledgeEntry).filter(
            SupportKnowledgeEntry.agency_id.is_(None)
        ).all()
        # These stay as global entries
        if orphan_kb:
            print(f"[SKIP] {len(orphan_kb)} knowledge entries kept as global (agency_id=NULL)")
        else:
            print("[SKIP] No knowledge entries found")

        session.commit()
        print("\n[SUCCESS] Multi-tenant migration completed successfully!")

    except Exception as exc:
        session.rollback()
        print(f"[ERROR] Migration failed: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    run()
