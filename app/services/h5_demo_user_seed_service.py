"""Seed a demo H5 member user on startup so that login works out of the box."""
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    H5Site,
    MemberProfile,
    UserIdentity,
    utc_now,
)

DEMO_PHONE = "13800000000"
DEMO_PASSWORD = "demo123456"
DEMO_SITE_KEY = "mall-cn"
DEMO_DISPLAY_NAME = "Demo User"


class H5DemoUserSeedService:
    """Creates a demo H5 member user if one does not already exist."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_demo_user(self) -> bool:
        """Return True if a new demo user was created, False if it already exists."""
        site = self._session.scalars(
            select(H5Site).where(H5Site.site_key == DEMO_SITE_KEY)
        ).first()
        if site is None:
            return False  # site not bootstrapped yet

        existing = self._session.scalars(
            select(UserIdentity).where(
                UserIdentity.identity_type == "phone",
                UserIdentity.identity_value == DEMO_PHONE,
            )
        ).first()
        if existing is not None:
            return False  # already seeded

        now = utc_now()
        password_salt = secrets.token_hex(16)
        password_hash = self._hash_password(DEMO_PASSWORD, password_salt)

        user = AppUser(
            account_id=site.account_id,
            public_user_id=f"h5-user-{secrets.token_hex(12)}",
            registration_site_id=site.id,
            display_name=DEMO_DISPLAY_NAME,
            language_code="zh-CN",
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=False,
            is_new_user=False,
            restrict_task_claim=False,
            last_active_at=now,
        )
        self._session.add(user)
        self._session.flush()

        member_no = self._generate_member_no(site.account_id)

        self._session.add(
            UserIdentity(
                user_id=user.id,
                identity_type="phone",
                identity_value=DEMO_PHONE,
                is_verified=True,
                is_primary=True,
            )
        )
        self._session.add(
            MemberProfile(
                account_id=site.account_id,
                user_id=user.id,
                member_no=member_no,
                password_hash=password_hash,
                password_salt=password_salt,
                password_updated_at=now,
                last_login_at=now,
            )
        )
        self._session.commit()
        return True

    def _generate_member_no(self, account_id: str) -> str:
        for _ in range(50):
            member_no = "".join(secrets.choice("0123456789") for _ in range(8))
            exists = self._session.scalars(
                select(MemberProfile.id).where(
                    MemberProfile.account_id == account_id,
                    MemberProfile.member_no == member_no,
                )
            ).first()
            if exists is None:
                return member_no
        raise RuntimeError(
            f"Unable to generate a unique member_no for account '{account_id}'."
        )

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            240_000,
        )
        return digest.hex()
