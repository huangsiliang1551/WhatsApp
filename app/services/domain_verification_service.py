"""DNS & SSL verification service for H5 site domains."""
from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import H5Site, UptimeCheck


class DomainVerificationService:
    """Verify DNS A records and SSL certificates for a site's domain."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def verify_domain(self, site_id: str) -> dict:
        """Verify DNS A record and SSL certificate for a site's domain."""
        site = self._session.get(H5Site, site_id)
        if site is None:
            raise LookupError(f"Site '{site_id}' not found.")

        domain = site.domain
        if not domain:
            return {
                "dns_valid": False,
                "a_record": None,
                "ssl_valid": False,
                "ssl_expires_at": None,
                "ssl_days_remaining": None,
            }

        # ── DNS A record lookup ──
        a_record: str | None = None
        dns_valid = False
        try:
            raw = socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
            if raw:
                a_record = raw[0][4][0]
                dns_valid = True
        except socket.gaierror:
            dns_valid = False

        # ── SSL certificate check ──
        ssl_valid = False
        ssl_expires_at: str | None = None
        ssl_days_remaining: int | None = None
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as tls:
                    cert = tls.getpeercert()
                    if cert and "notAfter" in cert:
                        expires = datetime.strptime(
                            cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
                        ).replace(tzinfo=UTC)
                        ssl_expires_at = expires.isoformat()
                        ssl_valid = expires > datetime.now(UTC)
                        ssl_days_remaining = (expires - datetime.now(UTC)).days
        except (ssl.SSLError, socket.timeout, ConnectionRefusedError, OSError):
            ssl_valid = False

        # ── Record an UptimeCheck entry for this verification ──
        uptime_status = "up" if dns_valid else "down"
        check = UptimeCheck(
            site_id=site_id,
            status=uptime_status,
            response_time_ms=None,
            status_code=200 if dns_valid else 0,
            error_message=None if dns_valid else "DNS resolution failed",
        )
        self._session.add(check)
        self._session.commit()

        return {
            "dns_valid": dns_valid,
            "a_record": a_record,
            "ssl_valid": ssl_valid,
            "ssl_expires_at": ssl_expires_at,
            "ssl_days_remaining": ssl_days_remaining,
        }
