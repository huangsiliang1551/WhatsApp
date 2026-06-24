from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import re
import secrets
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.settings import Settings
from app.db.models import (
    AppUser,
    H5Site,
    InviteCode,
    MemberAuthSession,
    MemberProfile,
    UserIdentity,
    UserReferral,
    utc_now,
)
from app.schemas.h5_member_auth import (
    H5MemberAuthResponse,
    H5MemberHomeResponse,
    H5MemberIdentityPayload,
    H5MemberLoginRequest,
    H5MemberRegisterRequest,
    H5MemberSessionPayload,
    H5MemberSitePayload,
    H5MemberTaskSummary,
    H5MemberWalletSummary,
)
from app.services.task_service import TaskService
from app.services.ticket_service import ACTIVE_TICKET_STATUSES, TicketService


@dataclass(slots=True)
class H5MemberContext:
    member_profile: MemberProfile
    user: AppUser
    site: H5Site
    phone: str
    auth_session: MemberAuthSession

    @property
    def account_id(self) -> str:
        return self.member_profile.account_id


@dataclass(slots=True)
class H5AuthTokens:
    session_token: str
    refresh_token: str
    session_expires_at: datetime
    refresh_expires_at: datetime


class H5MemberAuthService:
    def __init__(self, *, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._max_sessions_per_user = settings.h5_member_max_sessions_per_user
        self._lockout_threshold = settings.h5_member_login_lockout_threshold
        self._lockout_minutes = settings.h5_member_login_lockout_minutes
        self._login_failures: dict[str, list[float]] = {}

    async def register(
        self,
        payload: H5MemberRegisterRequest,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> tuple[H5MemberContext, H5AuthTokens]:
        if payload.password != payload.confirm_password:
            raise ValueError("Password and confirm_password do not match.")
        self._validate_password_strength(payload.password)

        site = self._require_site(payload.site_key)
        phone = self._normalize_phone(payload.phone)
        if self._find_phone_identity(phone) is not None:
            raise ValueError(f"Phone '{phone}' is already registered.")

        # ── 归属入口解析（spec 7.1-7.2） ──
        # entry_code 与 invite_code 互为别名，内部统一为 entry_code
        from app.services.member_ownership_service import (
            AttributionError,
            MemberAIOwnershipService,
            MemberOwnershipService,
        )

        entry_code_value = (payload.entry_code or payload.invite_code or "").strip() or None
        ownership_svc = MemberOwnershipService(self._session)
        entry_link, resolved_code = ownership_svc.resolve_registration_entry(
            site=site, entry_code_or_invite_code=entry_code_value
        )
        # entry_code_value 命中 EntryLink 时用 link；否则回退旧 InviteCode 逻辑
        invite_code = self._resolve_invite_code(site_id=site.id, code=resolved_code) if entry_link is None else None
        referrer_user_id = (
            invite_code.inviter_user_id
            if invite_code is not None and invite_code.inviter_user_id is not None
            else None
        )

        now = utc_now()
        password_salt = secrets.token_hex(16)
        user = AppUser(
            account_id=site.account_id,
            public_user_id=f"h5-user-{secrets.token_hex(12)}",
            registration_site_id=site.id,
            display_name=(payload.display_name or "").strip() or f"Member {phone[-4:]}",
            language_code=payload.language_code,
            is_anonymous=False,
            lifecycle_status="active",
            has_phone=True,
            has_email=False,
            has_whatsapp=False,
            is_invited_user=invite_code is not None,
            is_new_user=True,
            restrict_task_claim=False,
            registration_invite_code=invite_code.code if invite_code is not None else None,
            registration_ip=client_ip,
            last_active_at=now,
        )
        self._session.add(user)
        self._session.flush()

        self._session.add(
            UserIdentity(
                user_id=user.id,
                identity_type="phone",
                identity_value=phone,
                is_verified=True,
                is_primary=True,
            )
        )

        member_profile = MemberProfile(
            account_id=site.account_id,
            user_id=user.id,
            member_no=self._generate_member_no(site.account_id),
            password_hash=self._hash_password(payload.password, password_salt),
            password_salt=password_salt,
            password_updated_at=now,
            last_login_at=now,
        )
        self._session.add(member_profile)
        self._session.flush()
        self._ensure_member_invite_code(site_id=site.id, inviter_user_id=user.id)

        # ── 创建会员人力/AI 归属（spec 7.3-7.5） ──
        # 仅在有 entry_code 或站点强制 entry 时才解析归属；否则标记 unattributed
        # （spec 6.4：找不到归属时按配置标记 unattributed，不静默抛错）。
        if entry_link is not None or site.registration_entry_required or referrer_user_id:
            try:
                ownership_svc.assign_new_member_human_owner(
                    account_id=site.account_id,
                    user_id=user.id,
                    member_profile_id=member_profile.id,
                    entry_link=entry_link,
                    invite_code=invite_code.code if invite_code is not None else None,
                    referrer_user_id=referrer_user_id,
                    site=site,
                )
                ai_svc = MemberAIOwnershipService(self._session)
                ai_svc.assign_new_member_ai(
                    account_id=site.account_id,
                    user_id=user.id,
                    member_profile_id=member_profile.id,
                    entry_link=entry_link,
                    referrer_user_id=referrer_user_id,
                    site=site,
                )
            except AttributionError as exc:
                # 回滚已 flush 的 member/user，向上抛 400
                raise ValueError(str(exc)) from exc
        else:
            member_profile.attribution_status = "unattributed"
            self._session.add(member_profile)

        if invite_code is not None and invite_code.inviter_user_id is not None:
            invite_code.usage_count += 1
            self._session.add(invite_code)
            self._session.add(
                UserReferral(
                    account_id=site.account_id,
                    site_id=site.id,
                    invite_code=invite_code.code,
                    referrer_user_id=invite_code.inviter_user_id,
                    referred_user_id=user.id,
                    referred_member_profile_id=member_profile.id,
                    registered_at=now,
                    status="registered",
                )
            )

        auth_session, tokens = self._create_auth_session(
            member_profile=member_profile,
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        self._session.add(auth_session)
        self._session.commit()
        context = self._build_context(
            member_profile=member_profile,
            user=user,
            site=site,
            phone=phone,
            auth_session=auth_session,
        )
        return context, tokens

    async def login(
        self,
        payload: H5MemberLoginRequest,
        *,
        client_ip: str | None,
        user_agent: str | None,
    ) -> tuple[H5MemberContext, H5AuthTokens]:
        site = self._require_site(payload.site_key)
        phone = self._normalize_phone(payload.phone)

        lockout_key = f"login:{phone}:{client_ip or 'unknown'}"
        self._check_login_lockout(lockout_key)

        identity = self._find_phone_identity(phone)
        if identity is None:
            self._record_login_failure(lockout_key)
            raise LookupError("Phone or password is invalid.")

        user = self._load_user(identity.user_id)
        if user.registration_site_id != site.id:
            self._record_login_failure(lockout_key)
            raise PermissionError(f"Phone '{phone}' does not belong to site '{site.site_key}'.")
        if user.account_id != site.account_id:
            self._record_login_failure(lockout_key)
            raise PermissionError("Phone account scope does not match the current H5 site.")

        member_profile = self._require_member_profile(user.id, user.account_id)
        if not self._verify_password(payload.password, member_profile.password_salt, member_profile.password_hash):
            self._record_login_failure(lockout_key)
            raise LookupError("Phone or password is invalid.")

        self._clear_login_failures(lockout_key)

        now = utc_now()
        user.last_active_at = now
        member_profile.last_login_at = now
        self._ensure_member_invite_code(site_id=site.id, inviter_user_id=user.id)
        auth_session, tokens = self._create_auth_session(
            member_profile=member_profile,
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        self._session.add(user)
        self._session.add(member_profile)
        self._session.add(auth_session)
        self._session.commit()
        context = self._build_context(
            member_profile=member_profile,
            user=user,
            site=site,
            phone=phone,
            auth_session=auth_session,
        )
        return context, tokens

    async def logout(self, *, session_token: str | None, refresh_token: str | None) -> None:
        matched = self._find_auth_session(session_token=session_token, refresh_token=refresh_token)
        if matched is None:
            return
        matched.status = "revoked"
        matched.revoked_at = utc_now()
        self._session.add(matched)
        self._session.commit()

    async def refresh(
        self,
        *,
        refresh_token: str | None,
        client_ip: str | None,
        user_agent: str | None,
    ) -> tuple[H5MemberContext, H5AuthTokens]:
        auth_session = self._find_auth_session(refresh_token=refresh_token)
        if auth_session is None:
            raise LookupError("Refresh session is invalid.")
        if auth_session.status != "active" or auth_session.revoked_at is not None:
            raise PermissionError("Refresh session is no longer active.")
        if auth_session.refresh_expires_at <= utc_now():
            raise PermissionError("Refresh session has expired.")

        # Auto-renewal: if within the last 25% of validity, extend expiry instead of rotating
        now = utc_now()
        total_refresh_ttl = timedelta(days=self._settings.h5_member_refresh_ttl_days)
        remaining = auth_session.refresh_expires_at - now
        renewal_threshold = timedelta(seconds=total_refresh_ttl.total_seconds() * 0.25)
        if remaining <= renewal_threshold:
            auth_session.refresh_expires_at = now + total_refresh_ttl
            self._session.add(auth_session)
            self._session.commit()
            member_profile = self._require_member_profile_by_id(auth_session.member_profile_id)
            user = self._load_user(auth_session.user_id)
            site = self._require_user_site(user)
            phone = self._require_primary_phone(user.id)
            tokens = H5AuthTokens(
                session_token="",
                refresh_token="",
                session_expires_at=auth_session.expires_at,
                refresh_expires_at=auth_session.refresh_expires_at,
            )
            self._ensure_member_invite_code(site_id=site.id, inviter_user_id=user.id)
            context = self._build_context(
                member_profile=member_profile,
                user=user,
                site=site,
                phone=phone,
                auth_session=auth_session,
            )
            return context, tokens

        auth_session.status = "revoked"
        auth_session.revoked_at = utc_now()
        self._session.add(auth_session)

        member_profile = self._require_member_profile_by_id(auth_session.member_profile_id)
        user = self._load_user(auth_session.user_id)
        site = self._require_user_site(user)
        phone = self._require_primary_phone(user.id)
        new_session, tokens = self._create_auth_session(
            member_profile=member_profile,
            user=user,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        self._ensure_member_invite_code(site_id=site.id, inviter_user_id=user.id)
        self._session.add(new_session)
        self._session.commit()
        context = self._build_context(
            member_profile=member_profile,
            user=user,
            site=site,
            phone=phone,
            auth_session=new_session,
        )
        return context, tokens

    async def resolve_context(self, *, session_token: str | None) -> H5MemberContext:
        auth_session = self._find_auth_session(session_token=session_token)
        if auth_session is None:
            raise LookupError("Member session was not found.")
        if auth_session.status != "active" or auth_session.revoked_at is not None:
            raise PermissionError("Member session is no longer active.")
        if auth_session.expires_at <= utc_now():
            raise PermissionError("Member session has expired.")

        member_profile = self._require_member_profile_by_id(auth_session.member_profile_id)
        user = self._load_user(auth_session.user_id)
        site = self._require_user_site(user)
        phone = self._require_primary_phone(user.id)

        auth_session.last_seen_at = utc_now()
        self._ensure_member_invite_code(site_id=site.id, inviter_user_id=user.id)
        self._session.add(auth_session)
        self._session.commit()
        return self._build_context(
            member_profile=member_profile,
            user=user,
            site=site,
            phone=phone,
            auth_session=auth_session,
        )

    async def build_home_response(
        self,
        *,
        context: H5MemberContext,
        task_service: TaskService,
        ticket_service: TicketService,
    ) -> H5MemberHomeResponse:
        tasks = [
            item
            for item in await task_service.list_task_instances(user_id=context.user.id)
            if item.site_id == context.site.id
        ]
        task_summary = H5MemberTaskSummary(
            total=len(tasks),
            available=sum(1 for item in tasks if item.status == "available"),
            claimed=sum(1 for item in tasks if item.status == "claimed"),
            pending_review=sum(1 for item in tasks if item.status in {"submitted", "under_review", "pending_review"}),
            completed=sum(1 for item in tasks if item.status in {"approved", "completed"}),
            rejected=sum(1 for item in tasks if item.status in {"rejected", "appealing", "changes_requested"}),
        )
        tickets = await ticket_service.list_tickets(
            public_user_id=context.user.public_user_id,
            site_id=context.site.id,
            include_internal_messages=False,
        )
        open_ticket_count = sum(1 for item in tickets if item.status in ACTIVE_TICKET_STATUSES)
        return H5MemberHomeResponse(
            member=self._serialize_member(context),
            site=self._serialize_site(context.site),
            task_summary=task_summary,
            open_ticket_count=open_ticket_count,
            unread_message_count=0,
            wallet=H5MemberWalletSummary(),
        )

    def build_auth_response(self, context: H5MemberContext) -> H5MemberAuthResponse:
        return H5MemberAuthResponse(
            member=self._serialize_member(context),
            site=self._serialize_site(context.site),
            session=H5MemberSessionPayload(
                expires_at=context.auth_session.expires_at,
                refresh_expires_at=context.auth_session.refresh_expires_at,
            ),
        )

    def _create_auth_session(
        self,
        *,
        member_profile: MemberProfile,
        user: AppUser,
        client_ip: str | None,
        user_agent: str | None,
    ) -> tuple[MemberAuthSession, H5AuthTokens]:
        now = utc_now()
        session_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(48)
        session_expires_at = now + timedelta(hours=self._settings.h5_member_session_ttl_hours)
        refresh_expires_at = now + timedelta(days=self._settings.h5_member_refresh_ttl_days)
        auth_session = MemberAuthSession(
            account_id=member_profile.account_id,
            user_id=user.id,
            member_profile_id=member_profile.id,
            session_token_hash=self._hash_token(session_token),
            refresh_token_hash=self._hash_token(refresh_token),
            status="active",
            expires_at=session_expires_at,
            refresh_expires_at=refresh_expires_at,
            last_seen_at=now,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        self._enforce_max_sessions(user.id)
        return auth_session, H5AuthTokens(
            session_token=session_token,
            refresh_token=refresh_token,
            session_expires_at=session_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    def _find_phone_identity(self, phone: str) -> UserIdentity | None:
        return self._session.scalars(
            select(UserIdentity).where(
                UserIdentity.identity_type == "phone",
                UserIdentity.identity_value == phone,
            )
        ).first()

    def _find_auth_session(
        self,
        *,
        session_token: str | None = None,
        refresh_token: str | None = None,
    ) -> MemberAuthSession | None:
        if not session_token and not refresh_token:
            return None
        query = select(MemberAuthSession)
        if session_token:
            query = query.where(MemberAuthSession.session_token_hash == self._hash_token(session_token))
        if refresh_token:
            if session_token:
                query = query.where(MemberAuthSession.refresh_token_hash == self._hash_token(refresh_token))
            else:
                query = query.where(MemberAuthSession.refresh_token_hash == self._hash_token(refresh_token))
        return self._session.scalars(query.order_by(MemberAuthSession.created_at.desc())).first()

    def _load_user(self, user_id: str) -> AppUser:
        user = self._session.execute(
            select(AppUser)
            .options(joinedload(AppUser.registration_site))
            .options(selectinload(AppUser.identities))
            .where(AppUser.id == user_id)
        ).unique().scalars().first()
        if user is None:
            raise LookupError(f"User '{user_id}' was not found.")
        return user

    def _require_member_profile(self, user_id: str, account_id: str) -> MemberProfile:
        member_profile = self._session.scalars(
            select(MemberProfile).where(
                MemberProfile.user_id == user_id,
                MemberProfile.account_id == account_id,
            )
        ).first()
        if member_profile is None:
            raise LookupError(f"Member profile for user '{user_id}' was not found.")
        return member_profile

    def _require_member_profile_by_id(self, member_profile_id: str) -> MemberProfile:
        member_profile = self._session.get(MemberProfile, member_profile_id)
        if member_profile is None:
            raise LookupError(f"Member profile '{member_profile_id}' was not found.")
        return member_profile

    def _require_primary_phone(self, user_id: str) -> str:
        identity = self._session.scalars(
            select(UserIdentity)
            .where(
                UserIdentity.user_id == user_id,
                UserIdentity.identity_type == "phone",
            )
            .order_by(UserIdentity.is_primary.desc(), UserIdentity.created_at.asc())
        ).first()
        if identity is None:
            raise LookupError(f"Phone identity for user '{user_id}' was not found.")
        return identity.identity_value

    def _require_site(self, site_key: str) -> H5Site:
        site = self._session.scalars(select(H5Site).where(H5Site.site_key == site_key)).first()
        if site is None:
            raise LookupError(f"Site '{site_key}' was not found.")
        return site

    def _resolve_invite_code(self, *, site_id: str, code: str | None) -> InviteCode | None:
        normalized = (code or "").strip()
        if not normalized:
            return None
        invite_code = self._session.scalars(
            select(InviteCode).where(
                InviteCode.code == normalized,
                InviteCode.site_id == site_id,
            )
        ).first()
        if invite_code is None:
            raise LookupError(f"Invite code '{normalized}' was not found.")
        if invite_code.status != "active":
            raise ValueError(f"Invite code '{normalized}' is not active.")
        if invite_code.expires_at is not None and invite_code.expires_at <= utc_now():
            raise ValueError(f"Invite code '{normalized}' has expired.")
        if invite_code.usage_limit is not None and invite_code.usage_count >= invite_code.usage_limit:
            raise ValueError(f"Invite code '{normalized}' has reached the usage limit.")
        return invite_code

    def _ensure_member_invite_code(self, *, site_id: str, inviter_user_id: str) -> str:
        existing = self._session.scalars(
            select(InviteCode.code).where(
                InviteCode.site_id == site_id,
                InviteCode.inviter_user_id == inviter_user_id,
                InviteCode.status == "active",
            )
            .order_by(InviteCode.created_at.asc(), InviteCode.id.asc())
        ).first()
        if existing is not None:
            return existing

        for _ in range(50):
            code = f"INV-{secrets.token_hex(4).upper()}"
            taken = self._session.scalars(select(InviteCode.id).where(InviteCode.code == code)).first()
            if taken is not None:
                continue
            self._session.add(
                InviteCode(
                    code=code,
                    site_id=site_id,
                    inviter_user_id=inviter_user_id,
                    status="active",
                )
            )
            self._session.flush()
            return code
        raise RuntimeError("Unable to generate a unique member invite code.")

    @staticmethod
    def _require_user_site(user: AppUser) -> H5Site:
        site = user.registration_site
        if site is None:
            raise PermissionError("User is not bound to an H5 site.")
        return site

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
        raise RuntimeError(f"Unable to generate a unique member_no for account '{account_id}'.")

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        normalized = phone.strip().replace(" ", "").replace("-", "")
        if not normalized:
            raise ValueError("Phone cannot be empty.")
        return normalized

    @staticmethod
    def _mask_member_no(member_no: str) -> str:
        if len(member_no) <= 5:
            return member_no
        return f"{member_no[:3]}***{member_no[-2:]}"

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            240_000,
        )
        return digest.hex()

    @classmethod
    def _verify_password(cls, password: str, salt: str, expected_hash: str) -> bool:
        actual_hash = cls._hash_password(password, salt)
        return hmac.compare_digest(actual_hash, expected_hash)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_context(
        *,
        member_profile: MemberProfile,
        user: AppUser,
        site: H5Site,
        phone: str,
        auth_session: MemberAuthSession,
    ) -> H5MemberContext:
        return H5MemberContext(
            member_profile=member_profile,
            user=user,
            site=site,
            phone=phone,
            auth_session=auth_session,
        )

    @staticmethod
    def _serialize_site(site: H5Site) -> H5MemberSitePayload:
        return H5MemberSitePayload(
            id=site.id,
            account_id=site.account_id,
            site_key=site.site_key,
            brand_name=site.brand_name,
            domain=site.domain,
            default_language=site.default_language,
        )

    def _serialize_member(self, context: H5MemberContext) -> H5MemberIdentityPayload:
        invite_code = self._session.scalars(
            select(InviteCode.code)
            .where(
                InviteCode.site_id == context.site.id,
                InviteCode.inviter_user_id == context.user.id,
                InviteCode.status == "active",
            )
            .order_by(InviteCode.created_at.asc(), InviteCode.id.asc())
        ).first()
        return H5MemberIdentityPayload(
            user_id=context.user.id,
            public_user_id=context.user.public_user_id,
            account_id=context.account_id,
            site_id=context.site.id,
            site_key=context.site.site_key,
            member_no=context.member_profile.member_no,
            account_id_masked=self._mask_member_no(context.member_profile.member_no),
            invite_code=invite_code,
            phone=context.phone,
            display_name=context.user.display_name,
            language_code=context.user.language_code,
            created_at=context.member_profile.created_at,
            last_login_at=context.member_profile.last_login_at,
        )

    @staticmethod
    def _validate_password_strength(password: str) -> None:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[a-zA-Z]", password):
            raise ValueError("Password must contain at least one letter.")
        if not re.search(r"[0-9]", password):
            raise ValueError("Password must contain at least one number.")

    def _check_login_lockout(self, key: str) -> None:
        now = time.time()
        lockout_window = self._lockout_minutes * 60
        timestamps = self._login_failures.get(key, [])
        # Prune expired entries
        timestamps = [ts for ts in timestamps if now - ts < lockout_window]
        self._login_failures[key] = timestamps
        if len(timestamps) >= self._lockout_threshold:
            earliest = timestamps[0]
            retry_after = int(lockout_window - (now - earliest))
            raise PermissionError(
                f"Account is temporarily locked due to too many failed login attempts. "
                f"Try again in {max(1, retry_after)} seconds."
            )

    def _record_login_failure(self, key: str) -> None:
        now = time.time()
        lockout_window = self._lockout_minutes * 60
        timestamps = self._login_failures.get(key, [])
        timestamps = [ts for ts in timestamps if now - ts < lockout_window]
        timestamps.append(now)
        self._login_failures[key] = timestamps

    def _clear_login_failures(self, key: str) -> None:
        self._login_failures.pop(key, None)

    def _enforce_max_sessions(self, user_id: str) -> None:
        active_sessions = self._session.scalars(
            select(MemberAuthSession).where(
                MemberAuthSession.user_id == user_id,
                MemberAuthSession.status == "active",
                MemberAuthSession.revoked_at.is_(None),
            ).order_by(
                MemberAuthSession.created_at.asc(),
                MemberAuthSession.id.asc(),
            )
        ).all()
        if len(active_sessions) >= self._max_sessions_per_user:
            sessions_to_revoke = active_sessions[:len(active_sessions) - self._max_sessions_per_user + 1]
            revoke_now = utc_now()
            for old_session in sessions_to_revoke:
                old_session.status = "revoked"
                old_session.revoked_at = revoke_now
                self._session.add(old_session)
