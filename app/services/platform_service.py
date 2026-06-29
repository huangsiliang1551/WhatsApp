from decimal import Decimal

from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.db.models import (
    AppUser,
    AudienceRuleSet,
    Conversation,
    DeployHistory,
    H5Site,
    H5SiteConfig,
    H5Translation,
    InviteCode,
    MemberWhatsAppBindingRequest,
    SitePermission,
    Ticket,
    UserIdentity,
    UserTag,
    UserTagAssignment,
    WalletAccount,
)
from app.schemas.platform import (
    AudienceRuleSetCreateRequest,
    AudienceRuleSetResponse,
    AudienceRuleSetUpdateRequest,
    H5SiteConfigResponse,
    H5SiteConfigUpdateRequest,
    H5SiteCreateRequest,
    H5SiteResponse,
    H5SiteUpdateRequest,
    PlatformUserCreateRequest,
    PlatformUserEnhancedResponse,
    PlatformUserPaginatedResponse,
    PlatformUserResponse,
    UserIdentityCreateRequest,
    UserIdentityResponse,
    UserTagCreateRequest,
    UserTagCreateResponse,
    UserTagResponse,
)
from app.services.data_scope_filter_service import DataScopeFilterService
from app.core.auth import RequestActor


class PlatformService:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _build_user_search_clause(search: str) -> object:
        search_like = f"%{search}%"
        return or_(
            AppUser.public_user_id.ilike(search_like),
            AppUser.display_name.ilike(search_like),
            AppUser.registration_ip.ilike(search_like),
            AppUser.id.in_(
                select(UserIdentity.user_id).where(
                    UserIdentity.identity_value.ilike(search_like)
                )
            ),
            AppUser.id.in_(
                select(MemberWhatsAppBindingRequest.user_id).where(
                    MemberWhatsAppBindingRequest.requested_phone_number.ilike(search_like)
                )
            ),
        )

    async def list_sites(self, allowed_account_ids: set[str] | None = None) -> list[H5SiteResponse]:
        query = select(H5Site).order_by(H5Site.brand_name, H5Site.site_key)
        if allowed_account_ids is not None:
            query = query.where(H5Site.account_id.in_(sorted(allowed_account_ids)))
        sites = self._session.scalars(query).all()
        return [self._serialize_site(site) for site in sites]

    async def get_site(self, site_id: str) -> H5SiteResponse | None:
        site = self._session.get(H5Site, site_id)
        if site is None:
            return None
        return self._serialize_site(site)

    async def create_site(self, payload: H5SiteCreateRequest) -> H5SiteResponse:
        existing = self._session.scalars(
            select(H5Site).where((H5Site.site_key == payload.site_key) | (H5Site.domain == payload.domain))
        ).first()
        if existing is not None:
            raise ValueError("Site key or domain already exists.")

        site = H5Site(
            account_id=payload.account_id,
            site_key=payload.site_key,
            domain=payload.domain,
            brand_name=payload.brand_name,
            logo_url=payload.logo_url,
            default_language=payload.default_language,
            status=payload.status,
            metadata_json=self._with_default_site_template(payload.metadata_json),
        )
        self._session.add(site)
        self._session.flush()

        self._session.commit()
        self._session.refresh(site)
        return self._serialize_site(site)

    async def update_site(self, site_id: str, payload: H5SiteUpdateRequest) -> H5SiteResponse:
        site = self._session.get(H5Site, site_id)
        if site is None:
            raise ValueError("Site not found.")

        if payload.brand_name is not None:
            site.brand_name = payload.brand_name
        if payload.domain is not None:
            existing = self._session.scalars(
                select(H5Site).where(H5Site.domain == payload.domain, H5Site.id != site_id)
            ).first()
            if existing is not None:
                raise ValueError("Domain already exists.")
            site.domain = payload.domain
        if payload.logo_url is not None:
            site.logo_url = payload.logo_url
        if payload.default_language is not None:
            site.default_language = payload.default_language
        if payload.status is not None:
            site.status = payload.status
        if payload.metadata_json is not None:
            site.metadata_json = self._with_default_site_template(payload.metadata_json)

        self._session.commit()
        self._session.refresh(site)
        return self._serialize_site(site)

    async def delete_site(self, site_id: str) -> str | None:
        site = self._session.get(H5Site, site_id)
        if site is None:
            raise ValueError("Site not found.")
        account_id = site.account_id
        site.status = "archived"
        self._session.commit()
        return account_id

    async def get_site_config(self, site_id: str) -> H5SiteConfigResponse | None:
        config = self._session.scalars(
            select(H5SiteConfig).where(H5SiteConfig.site_id == site_id)
        ).first()
        if config is None:
            return None
        return H5SiteConfigResponse.model_validate({
            "id": config.id,
            "site_id": config.site_id,
            "logo_url": config.logo_url,
            "favicon_url": config.favicon_url,
            "primary_color": config.primary_color,
            "font_family": config.font_family,
            "footer_text": config.footer_text,
            "enabled_pages": config.enabled_pages,
            "custom_css": config.custom_css,
            "deploy_type": config.deploy_type,
            "ssh_host": config.ssh_host,
            "ssh_user": config.ssh_user,
            "ssh_key_path": config.ssh_key_path,
            "domain": config.domain,
            "ssl_enabled": config.ssl_enabled,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        })

    async def update_site_config(self, site_id: str, payload: H5SiteConfigUpdateRequest) -> H5SiteConfigResponse:
        config = self._session.scalars(
            select(H5SiteConfig).where(H5SiteConfig.site_id == site_id)
        ).first()
        if config is None:
            config = H5SiteConfig(id=str(uuid4()), site_id=site_id)
            self._session.add(config)

        if payload.logo_url is not None:
            config.logo_url = payload.logo_url
        if payload.favicon_url is not None:
            config.favicon_url = payload.favicon_url
        if payload.primary_color is not None:
            config.primary_color = payload.primary_color
        if payload.font_family is not None:
            config.font_family = payload.font_family
        if payload.footer_text is not None:
            config.footer_text = payload.footer_text
        if payload.enabled_pages is not None:
            config.enabled_pages = payload.enabled_pages
        if payload.custom_css is not None:
            config.custom_css = payload.custom_css
        if payload.deploy_type is not None:
            config.deploy_type = payload.deploy_type
        if payload.ssh_host is not None:
            config.ssh_host = payload.ssh_host
        if payload.ssh_user is not None:
            config.ssh_user = payload.ssh_user
        if payload.ssh_key_path is not None:
            config.ssh_key_path = payload.ssh_key_path
        if payload.domain is not None:
            config.domain = payload.domain
        if payload.ssl_enabled is not None:
            config.ssl_enabled = payload.ssl_enabled

        self._session.commit()
        self._session.refresh(config)
        return H5SiteConfigResponse.model_validate({
            "id": config.id,
            "site_id": config.site_id,
            "logo_url": config.logo_url,
            "favicon_url": config.favicon_url,
            "primary_color": config.primary_color,
            "font_family": config.font_family,
            "footer_text": config.footer_text,
            "enabled_pages": config.enabled_pages,
            "custom_css": config.custom_css,
            "deploy_type": config.deploy_type,
            "ssh_host": config.ssh_host,
            "ssh_user": config.ssh_user,
            "ssh_key_path": config.ssh_key_path,
            "domain": config.domain,
            "ssl_enabled": config.ssl_enabled,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        })

    async def list_tags(self, is_active: bool | None = None) -> list[UserTagCreateResponse]:
        query = select(UserTag).order_by(UserTag.name, UserTag.tag_key)
        if is_active is not None:
            query = query.where(UserTag.is_active == is_active)
        tags = self._session.scalars(query).all()
        return [self._serialize_tag(tag) for tag in tags]

    async def create_tag(self, payload: UserTagCreateRequest, created_by: str | None) -> UserTagCreateResponse:
        existing = self._session.scalars(select(UserTag).where(UserTag.tag_key == payload.tag_key)).first()
        if existing is not None:
            raise ValueError(f"Tag key '{payload.tag_key}' already exists.")

        tag = UserTag(
            tag_key=payload.tag_key,
            name=payload.name,
            description=payload.description,
            color=payload.color,
            source_type=payload.source_type,
            rule_json=payload.rule_json,
            is_active=payload.is_active,
            created_by=created_by,
        )
        self._session.add(tag)
        self._session.commit()
        self._session.refresh(tag)
        return self._serialize_tag(tag)

    async def list_users(
        self,
        registration_site_id: str | None = None,
        lifecycle_status: str | None = None,
        is_anonymous: bool | None = None,
        allowed_account_ids: set[str] | None = None,
    ) -> list[PlatformUserResponse]:
        query = (
            select(AppUser)
            .options(selectinload(AppUser.registration_site))
            .options(selectinload(AppUser.identities))
            .options(selectinload(AppUser.tag_assignments).selectinload(UserTagAssignment.tag))
            .order_by(AppUser.created_at.desc(), AppUser.public_user_id)
        )
        if registration_site_id is not None:
            query = query.where(AppUser.registration_site_id == registration_site_id)
        if lifecycle_status is not None:
            query = query.where(AppUser.lifecycle_status == lifecycle_status)
        if is_anonymous is not None:
            query = query.where(AppUser.is_anonymous == is_anonymous)
        if allowed_account_ids is not None:
            query = query.where(AppUser.account_id.in_(sorted(allowed_account_ids)))

        users = self._session.scalars(query).all()
        return [self._serialize_user(user) for user in users]

    async def list_users_enhanced(
        self,
        page: int | None = None,
        size: int = 20,
        sort: str = "created_at:desc",
        search: str | None = None,
        account_id: str | None = None,
        has_whatsapp: bool | None = None,
        lifecycle_status: str | None = None,
        registration_site_id: str | None = None,
        is_anonymous: bool | None = None,
        allowed_account_ids: set[str] | None = None,
        scope_actor: RequestActor | None = None,
    ) -> PlatformUserPaginatedResponse | list[PlatformUserResponse]:
        """
        Enhanced user listing with pagination, search, and aggregate fields.

        When ``page`` is None, returns the full list (backward compatible).
        """
        base_query = select(AppUser)

        # ── Filters ──────────────────────────────────────────────────
        if registration_site_id is not None:
            base_query = base_query.where(AppUser.registration_site_id == registration_site_id)
        if lifecycle_status is not None:
            base_query = base_query.where(AppUser.lifecycle_status == lifecycle_status)
        if is_anonymous is not None:
            base_query = base_query.where(AppUser.is_anonymous == is_anonymous)
        if allowed_account_ids is not None:
            base_query = base_query.where(AppUser.account_id.in_(sorted(allowed_account_ids)))
        if account_id is not None:
            base_query = base_query.where(AppUser.account_id == account_id)
        if has_whatsapp is not None:
            base_query = base_query.where(AppUser.has_whatsapp == has_whatsapp)

        # ── Search ───────────────────────────────────────────────────
        if search:
            base_query = base_query.where(self._build_user_search_clause(search))

        if scope_actor is not None:
            base_query = DataScopeFilterService(self._session).filter_customers(base_query, scope_actor)

        # ── Sort ─────────────────────────────────────────────────────
        sort_field = "created_at"
        sort_dir = "desc"
        if ":" in sort:
            parts = sort.split(":", 1)
            sort_field = parts[0]
            sort_dir = parts[1] if len(parts) > 1 else "desc"

        sort_column = getattr(AppUser, sort_field, AppUser.created_at)
        order_fn = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        base_query = base_query.order_by(order_fn, AppUser.public_user_id)

        # ── Pagination / Full list ───────────────────────────────────
        if page is None:
            # Backward compatible: return full list
            query = base_query.options(
                selectinload(AppUser.registration_site),
                selectinload(AppUser.identities),
                selectinload(AppUser.tag_assignments).selectinload(UserTagAssignment.tag),
            )
            users = self._session.scalars(query).all()
            return [self._serialize_user(user) for user in users]

        # Total count — build independent query to avoid whereclause issues
        total = self._session.scalar(select(func.count()).select_from(base_query.subquery())) or 0

        # Paginated query
        offset = (page - 1) * size
        ids_query = base_query.with_only_columns(AppUser.id).offset(offset).limit(size)
        user_ids = [row[0] for row in self._session.execute(ids_query).all()]

        if not user_ids:
            return PlatformUserPaginatedResponse(items=[], total=total, page=page, size=size)

        # Load full users with relationships
        load_query = (
            select(AppUser)
            .options(
                selectinload(AppUser.registration_site),
                selectinload(AppUser.identities),
                selectinload(AppUser.tag_assignments).selectinload(UserTagAssignment.tag),
            )
            .where(AppUser.id.in_(user_ids))
            .order_by(order_fn, AppUser.public_user_id)
        )
        users = list(self._session.scalars(load_query).all())
        user_id_set = list({u.id for u in users})

        # ── Aggregate fields ─────────────────────────────────────────
        # Conversation counts (group by customer_id + status, aggregate in Python)
        conv_raw = self._session.execute(
            select(
                Conversation.customer_id,
                Conversation.status,
                func.count().label("cnt"),
            )
            .where(Conversation.customer_id.in_(user_id_set))
            .group_by(Conversation.customer_id, Conversation.status)
        ).all()
        conv_counts: dict[str, int] = {}
        conv_open_counts: dict[str, int] = {}
        for row in conv_raw:
            cid = row[0]
            conv_counts[cid] = conv_counts.get(cid, 0) + row[2]
            if row[1] == "open":
                conv_open_counts[cid] = conv_open_counts.get(cid, 0) + row[2]

        # Ticket counts
        ticket_raw = self._session.execute(
            select(
                Ticket.user_id,
                func.count().label("cnt"),
            )
            .where(Ticket.user_id.in_(user_id_set))
            .group_by(Ticket.user_id)
        ).all()
        ticket_counts: dict[str, int] = {}
        for row in ticket_raw:
            ticket_counts[row[0]] = row[1]

        # Wallet balances
        wallet_raw = self._session.execute(
            select(
                WalletAccount.user_id,
                WalletAccount.system_balance,
                WalletAccount.task_balance,
            )
            .where(WalletAccount.user_id.in_(user_id_set))
        ).all()
        wallet_balances: dict[str, float] = {}
        for row in wallet_raw:
            wallet_balances[row[0]] = float((row[1] or Decimal("0")) + (row[2] or Decimal("0")))

        # ── Build enhanced responses ─────────────────────────────────
        items: list[PlatformUserEnhancedResponse] = []
        for user in users:
            base = self._serialize_user(user)
            enhanced = PlatformUserEnhancedResponse(
                **base.model_dump(),
                conversation_count=conv_counts.get(user.id, 0),
                open_conversation_count=conv_open_counts.get(user.id, 0),
                ticket_count=ticket_counts.get(user.id, 0),
                wallet_balance=wallet_balances.get(user.id, 0.0),
            )
            items.append(enhanced)

        return PlatformUserPaginatedResponse(
            items=items, total=total, page=page, size=size
        )

    def resolve_create_user_account_id(self, payload: PlatformUserCreateRequest) -> str:
        site: H5Site | None = None
        if payload.registration_site_id is not None:
            site = self._session.get(H5Site, payload.registration_site_id)
            if site is None:
                raise LookupError(f"Site '{payload.registration_site_id}' was not found.")

        invite_code: InviteCode | None = None
        if payload.registration_invite_code is not None:
            invite_code = self._session.scalars(
                select(InviteCode).where(InviteCode.code == payload.registration_invite_code)
            ).first()
            if invite_code is None:
                raise LookupError(f"Invite code '{payload.registration_invite_code}' was not found.")

        site_account_id = site.account_id if site is not None else None
        invite_site: H5Site | None = None
        if invite_code is not None and invite_code.site_id is not None:
            invite_site = self._session.get(H5Site, invite_code.site_id)
        invite_account_id = invite_site.account_id if invite_site is not None else None

        if site_account_id is not None and invite_account_id is not None and site_account_id != invite_account_id:
            raise ValueError("User registration site account scope does not match the invite code site account scope.")
        if payload.account_id is not None and site_account_id is not None and payload.account_id != site_account_id:
            raise ValueError("User account_id does not match the registration site account scope.")
        if payload.account_id is not None and invite_account_id is not None and payload.account_id != invite_account_id:
            raise ValueError("User account_id does not match the invite code account scope.")

        resolved_account_id = payload.account_id or site_account_id or invite_account_id
        if resolved_account_id is None:
            raise ValueError("User requires a resolved account scope from payload, registration site, or invite code.")
        return resolved_account_id

    async def delete_user(self, user_id: str) -> None:
        """Delete a platform user by ID."""
        user = self._session.get(AppUser, user_id)
        if user is None:
            raise LookupError(f"User '{user_id}' was not found.")
        self._session.delete(user)
        self._session.commit()

    async def create_user(self, payload: PlatformUserCreateRequest) -> PlatformUserResponse:
        if self._session.scalars(select(AppUser).where(AppUser.public_user_id == payload.public_user_id)).first():
            raise ValueError(f"User '{payload.public_user_id}' already exists.")

        site: H5Site | None = None
        if payload.registration_site_id is not None:
            site = self._session.get(H5Site, payload.registration_site_id)
            if site is None:
                raise LookupError(f"Site '{payload.registration_site_id}' was not found.")
        resolved_account_id = self.resolve_create_user_account_id(payload)

        invite_code: InviteCode | None = None
        if payload.registration_invite_code is not None:
            invite_code = self._session.scalars(
                select(InviteCode).where(InviteCode.code == payload.registration_invite_code)
            ).first()
            if invite_code is None:
                raise LookupError(f"Invite code '{payload.registration_invite_code}' was not found.")
            if invite_code.site_id is not None:
                invite_site = self._session.get(H5Site, invite_code.site_id)
                if site is not None and invite_site is not None and invite_site.id != site.id:
                    raise ValueError("User registration site does not match the invite code site.")
                if site is None:
                    site = invite_site

        identities = self._normalize_identity_payloads(payload.identities)
        tag_assignments = self._resolve_tags(payload.tag_keys)

        user = AppUser(
            account_id=resolved_account_id,
            public_user_id=payload.public_user_id,
            registration_site_id=site.id if site is not None else None,
            display_name=payload.display_name,
            country_code=payload.country_code,
            language_code=payload.language_code,
            is_anonymous=payload.is_anonymous,
            lifecycle_status=payload.lifecycle_status,
            has_phone=any(item.identity_type == "phone" for item in identities),
            has_email=any(item.identity_type == "email" for item in identities),
            has_whatsapp=any(item.identity_type == "whatsapp" for item in identities),
            is_invited_user=invite_code is not None,
            is_new_user=True,
            restrict_task_claim=payload.restrict_task_claim,
            registration_invite_code=payload.registration_invite_code,
            registration_ip=payload.registration_ip,
        )
        self._session.add(user)
        self._session.flush()

        for identity in identities:
            self._session.add(
                UserIdentity(
                    user_id=user.id,
                    identity_type=identity.identity_type,
                    identity_value=identity.identity_value,
                    country_code=identity.country_code,
                    is_verified=identity.is_verified,
                    is_primary=identity.is_primary,
                    metadata_json=identity.metadata_json,
                )
            )

        for tag in tag_assignments:
            self._session.add(
                UserTagAssignment(
                    user_id=user.id,
                    tag_id=tag.id,
                    source_type=tag.source_type,
                )
            )

        if invite_code is not None:
            invite_code.usage_count += 1
            self._session.add(invite_code)

        self._session.commit()
        created_user = self._session.scalars(
            select(AppUser)
            .options(selectinload(AppUser.registration_site))
            .options(selectinload(AppUser.identities))
            .options(selectinload(AppUser.tag_assignments).selectinload(UserTagAssignment.tag))
            .where(AppUser.id == user.id)
        ).first()
        if created_user is None:
            raise LookupError(f"User '{user.id}' was not found after creation.")

        # 串联任务触发引擎：新用户注册触发 register 类型任务规则
        try:
            from app.services.task_engine import TaskEngine
            engine = TaskEngine(self._session)
            engine.on_user_registered(user_id=user.id, account_id=user.account_id)
        except Exception as exc:
            import structlog
            structlog.get_logger().warning(
                "task_trigger_on_register_failed",
                user_id=user.id,
                account_id=user.account_id,
                error=str(exc),
            )

        return self._serialize_user(created_user)

    async def list_audience_rule_sets(
        self,
        scope_type: str | None = None,
        status: str | None = None,
    ) -> list[AudienceRuleSetResponse]:
        query = select(AudienceRuleSet).order_by(AudienceRuleSet.created_at.desc(), AudienceRuleSet.rule_key)
        if scope_type is not None:
            query = query.where(AudienceRuleSet.scope_type == scope_type)
        if status is not None:
            query = query.where(AudienceRuleSet.status == status)
        rules = self._session.scalars(query).all()
        return [self._serialize_audience_rule(rule) for rule in rules]

    async def create_audience_rule_set(
        self,
        payload: AudienceRuleSetCreateRequest,
        created_by: str | None,
    ) -> AudienceRuleSetResponse:
        existing = self._session.scalars(
            select(AudienceRuleSet).where(AudienceRuleSet.rule_key == payload.rule_key)
        ).first()
        if existing is not None:
            raise ValueError(f"Audience rule key '{payload.rule_key}' already exists.")

        rule = AudienceRuleSet(
            rule_key=payload.rule_key,
            name=payload.name,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            status=payload.status,
            description=payload.description,
            rules_json=payload.rules_json,
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(rule)
        self._session.commit()
        self._session.refresh(rule)
        return self._serialize_audience_rule(rule)

    async def update_audience_rule_set(
        self,
        rule_set_id: str,
        payload: AudienceRuleSetUpdateRequest,
        updated_by: str | None,
    ) -> AudienceRuleSetResponse:
        """Update an audience rule set by ID. Returns updated rule or raises LookupError."""
        rule = self._session.get(AudienceRuleSet, rule_set_id)
        if rule is None:
            raise LookupError(f"Audience rule set '{rule_set_id}' was not found.")

        if payload.name is not None:
            rule.name = payload.name
        if payload.scope_type is not None:
            rule.scope_type = payload.scope_type
        if payload.scope_id is not None:
            rule.scope_id = payload.scope_id
        if payload.status is not None:
            rule.status = payload.status
        if payload.description is not None:
            rule.description = payload.description
        if payload.rules_json is not None:
            rule.rules_json = payload.rules_json
        rule.updated_by = updated_by

        self._session.commit()
        self._session.refresh(rule)
        return self._serialize_audience_rule(rule)

    async def delete_audience_rule_set(self, rule_set_id: str) -> None:
        """Delete an audience rule set by ID. Raises LookupError if not found."""
        rule = self._session.get(AudienceRuleSet, rule_set_id)
        if rule is None:
            raise LookupError(f"Audience rule set '{rule_set_id}' was not found.")
        self._session.delete(rule)
        self._session.commit()

    # ──────────────────────────────────────────────
    # SITE-BE-002: Clone Site
    # ──────────────────────────────────────────────
    async def clone_site(
        self,
        source_site_id: str,
        new_site_key: str,
        new_brand_name: str,
        new_domain: str,
        clone_brand_config: bool = True,
        clone_deploy_config: bool = True,
        clone_translations: bool = False,
        clone_permissions: bool = False,
    ) -> dict:
        """Clone a site's configuration to create a new site."""
        source = self._session.get(H5Site, source_site_id)
        if source is None:
            raise LookupError(f"Source site '{source_site_id}' not found.")

        # Check uniqueness
        existing = self._session.scalars(
            select(H5Site).where(
                (H5Site.site_key == new_site_key) | (H5Site.domain == new_domain)
            )
        ).first()
        if existing is not None:
            raise ValueError("Site key or domain already exists.")

        # Create new site based on source
        new_site = H5Site(
            account_id=source.account_id,
            site_key=new_site_key,
            domain=new_domain,
            brand_name=new_brand_name,
            logo_url=source.logo_url,
            default_language=source.default_language,
            status=source.status,
            metadata_json=self._with_default_site_template(source.metadata_json),
        )
        self._session.add(new_site)
        self._session.flush()

        # Clone H5SiteConfig (brand + deploy)
        source_config = self._session.scalar(
            select(H5SiteConfig).where(H5SiteConfig.site_id == source_site_id)
        )
        if source_config is not None:
            new_config = H5SiteConfig(
                site_id=new_site.id,
                logo_url=source_config.logo_url if clone_brand_config else None,
                favicon_url=source_config.favicon_url if clone_brand_config else None,
                primary_color=source_config.primary_color if clone_brand_config else "#1677ff",
                font_family=source_config.font_family if clone_brand_config else None,
                footer_text=source_config.footer_text if clone_brand_config else None,
                enabled_pages=source_config.enabled_pages if clone_brand_config else None,
                custom_css=source_config.custom_css if clone_brand_config else None,
                deploy_type=source_config.deploy_type if clone_deploy_config else None,
                ssh_host=source_config.ssh_host if clone_deploy_config else None,
                ssh_user=source_config.ssh_user if clone_deploy_config else None,
                ssh_key_path=source_config.ssh_key_path if clone_deploy_config else None,
                domain=new_domain,
                ssl_enabled=source_config.ssl_enabled if clone_deploy_config else True,
            )
            self._session.add(new_config)

        # Clone translations (only structure)
        if clone_translations:
            translations = self._session.scalars(
                select(H5Translation).where(H5Translation.site_id == source_site_id)
            ).all()
            for t in translations:
                new_t = H5Translation(
                    site_id=new_site.id,
                    language_code=t.language_code,
                    translation_key=t.translation_key,
                    translated_text=t.translated_text,
                    is_ai_translated=False,
                )
                self._session.add(new_t)

        # Clone permissions
        if clone_permissions:
            perms = self._session.scalars(
                select(SitePermission).where(SitePermission.site_id == source_site_id)
            ).all()
            for p in perms:
                new_p = SitePermission(
                    user_id=p.user_id,
                    site_id=new_site.id,
                )
                self._session.add(new_p)

        self._session.commit()
        self._session.refresh(new_site)
        return self._serialize_site(new_site).model_dump(mode="json")

    # ──────────────────────────────────────────────
    # SITE-BE-003: Export / Import Config
    # ──────────────────────────────────────────────
    async def export_config(self, site_id: str) -> dict:
        """Export site configuration as a JSON-serializable dict."""
        site = self._session.get(H5Site, site_id)
        if site is None:
            raise LookupError(f"Site '{site_id}' not found.")

        config = self._session.scalar(
            select(H5SiteConfig).where(H5SiteConfig.site_id == site_id)
        )

        translations = self._session.scalars(
            select(H5Translation).where(H5Translation.site_id == site_id)
        ).all()

        permissions = self._session.scalars(
            select(SitePermission).where(SitePermission.site_id == site_id)
        ).all()

        return {
            "site": {
                "site_key": site.site_key,
                "domain": site.domain,
                "brand_name": site.brand_name,
                "logo_url": site.logo_url,
                "default_language": site.default_language,
                "status": site.status,
                "metadata_json": site.metadata_json,
            },
            "config": {
                "logo_url": config.logo_url,
                "favicon_url": config.favicon_url,
                "primary_color": config.primary_color,
                "font_family": config.font_family,
                "footer_text": config.footer_text,
                "enabled_pages": config.enabled_pages,
                "custom_css": config.custom_css,
                "deploy_type": config.deploy_type,
                "ssh_host": config.ssh_host,
                "ssh_user": config.ssh_user,
                "ssh_key_path": config.ssh_key_path,
                "ssl_enabled": config.ssl_enabled,
            } if config else None,
            "translations": [
                {
                    "language_code": t.language_code,
                    "translation_key": t.translation_key,
                    "translated_text": t.translated_text,
                }
                for t in translations
            ],
            "permissions": [
                {"user_id": p.user_id} for p in permissions
            ],
        }

    async def import_config(self, payload: dict, account_id: str) -> dict:
        """Import a site configuration export and create a new site."""
        site_data = payload.get("site", {})
        if not site_data.get("site_key") or not site_data.get("domain") or not site_data.get("brand_name"):
            raise ValueError("site_key, domain, and brand_name are required.")

        existing = self._session.scalars(
            select(H5Site).where(
                (H5Site.site_key == site_data["site_key"]) | (H5Site.domain == site_data["domain"])
            )
        ).first()
        if existing is not None:
            raise ValueError("Site key or domain already exists.")

        site = H5Site(
            account_id=account_id,
            site_key=site_data["site_key"],
            domain=site_data["domain"],
            brand_name=site_data["brand_name"],
            logo_url=site_data.get("logo_url"),
            default_language=site_data.get("default_language", "zh-CN"),
            status=site_data.get("status", "active"),
            metadata_json=self._with_default_site_template(site_data.get("metadata_json")),
        )
        self._session.add(site)
        self._session.flush()

        # Import config
        config_data = payload.get("config")
        if config_data:
            cfg = H5SiteConfig(
                site_id=site.id,
                logo_url=config_data.get("logo_url"),
                favicon_url=config_data.get("favicon_url"),
                primary_color=config_data.get("primary_color", "#1677ff"),
                font_family=config_data.get("font_family"),
                footer_text=config_data.get("footer_text"),
                enabled_pages=config_data.get("enabled_pages"),
                custom_css=config_data.get("custom_css"),
                deploy_type=config_data.get("deploy_type"),
                ssh_host=config_data.get("ssh_host"),
                ssh_user=config_data.get("ssh_user"),
                ssh_key_path=config_data.get("ssh_key_path"),
                domain=site.domain,
                ssl_enabled=config_data.get("ssl_enabled", True),
            )
            self._session.add(cfg)

        # Import translations
        for t_data in payload.get("translations", []):
            trans = H5Translation(
                site_id=site.id,
                language_code=t_data["language_code"],
                translation_key=t_data["translation_key"],
                translated_text=t_data.get("translated_text", ""),
                is_ai_translated=False,
            )
            self._session.add(trans)

        # Import permissions
        for p_data in payload.get("permissions", []):
            if p_data.get("user_id"):
                perm = SitePermission(
                    user_id=p_data["user_id"],
                    site_id=site.id,
                )
                self._session.add(perm)

        self._session.commit()
        self._session.refresh(site)
        return self._serialize_site(site).model_dump(mode="json")

    # ──────────────────────────────────────────────
    # SITE-BE-004: Batch Update
    # ──────────────────────────────────────────────
    async def batch_update(
        self,
        site_ids: list[str],
        action: str,
        config: dict | None = None,
    ) -> dict:
        """Perform batch action on multiple sites.

        Actions: pause | resume | delete | update_config
        """
        results: list[dict] = []
        errors: list[dict] = []

        for site_id in site_ids:
            try:
                site = self._session.get(H5Site, site_id)
                if site is None:
                    errors.append({"site_id": site_id, "error": "Site not found"})
                    continue

                if action == "pause":
                    site.status = "paused"
                elif action == "resume":
                    site.status = "active"
                elif action == "delete":
                    site.status = "archived"
                elif action == "update_config" and config:
                    site_config = self._session.scalar(
                        select(H5SiteConfig).where(H5SiteConfig.site_id == site_id)
                    )
                    if site_config is None:
                        site_config = H5SiteConfig(site_id=site_id)
                        self._session.add(site_config)
                        self._session.flush()
                    for key, value in config.items():
                        if hasattr(site_config, key):
                            setattr(site_config, key, value)
                else:
                    errors.append({"site_id": site_id, "error": f"Unsupported action '{action}'"})
                    continue

                results.append({"site_id": site_id, "status": "ok"})
            except Exception as exc:
                errors.append({"site_id": site_id, "error": str(exc)})

        self._session.commit()
        return {"results": results, "errors": errors}

    def _normalize_identity_payloads(
        self,
        identities: list[UserIdentityCreateRequest],
    ) -> list[UserIdentityCreateRequest]:
        seen_values: set[tuple[str, str]] = set()
        normalized: list[UserIdentityCreateRequest] = []
        for identity in identities:
            key = (identity.identity_type, identity.identity_value)
            if key in seen_values:
                raise ValueError("Duplicate identities are not allowed in a single user payload.")
            seen_values.add(key)

            existing = self._session.scalars(
                select(UserIdentity).where(
                    UserIdentity.identity_type == identity.identity_type,
                    UserIdentity.identity_value == identity.identity_value,
                )
            ).first()
            if existing is not None:
                raise ValueError(
                    f"Identity '{identity.identity_type}:{identity.identity_value}' already exists."
                )
            normalized.append(identity)
        return normalized

    def _resolve_tags(self, tag_keys: list[str]) -> list[UserTag]:
        if not tag_keys:
            return []
        tags = self._session.scalars(select(UserTag).where(UserTag.tag_key.in_(tag_keys))).all()
        found = {tag.tag_key for tag in tags}
        missing = sorted(set(tag_keys) - found)
        if missing:
            raise LookupError(f"Unknown tags: {', '.join(missing)}.")
        return sorted(tags, key=lambda item: item.tag_key)

    def _serialize_site(self, site: H5Site) -> H5SiteResponse:
        return H5SiteResponse.model_validate(
            {
                "id": site.id,
                "account_id": site.account_id,
                "site_key": site.site_key,
                "domain": site.domain,
                "brand_name": site.brand_name,
                "logo_url": site.logo_url,
                "default_language": site.default_language,
                "status": site.status,
                "metadata_json": site.metadata_json,
                "created_at": site.created_at,
                "updated_at": site.updated_at,
            }
        )

    def _with_default_site_template(self, metadata_json: dict[str, object] | None) -> dict[str, object]:
        metadata = dict(metadata_json or {})
        metadata["template_id"] = DEFAULT_H5_TEMPLATE_ID
        return metadata

    def _serialize_tag(self, tag: UserTag) -> UserTagCreateResponse:
        return UserTagCreateResponse.model_validate(
            {
                "id": tag.id,
                "tag_key": tag.tag_key,
                "name": tag.name,
                "description": tag.description,
                "color": tag.color,
                "source_type": tag.source_type,
                "rule_json": tag.rule_json,
                "is_active": tag.is_active,
                "created_by": tag.created_by,
                "created_at": tag.created_at,
                "updated_at": tag.updated_at,
            }
        )

    def _serialize_user(self, user: AppUser) -> PlatformUserResponse:
        tags: list[UserTagResponse] = []
        for assignment in user.tag_assignments:
            tag = assignment.tag
            tags.append(
                UserTagResponse.model_validate(
                    {
                        "tag_key": tag.tag_key,
                        "name": tag.name,
                        "description": tag.description,
                        "color": tag.color,
                        "source_type": assignment.source_type,
                        "is_active": tag.is_active,
                    }
                )
            )

        return PlatformUserResponse.model_validate(
            {
                "id": user.id,
                "account_id": user.account_id,
                "public_user_id": user.public_user_id,
                "registration_site_id": user.registration_site_id,
                "registration_site_key": user.registration_site.site_key if user.registration_site else None,
                "registration_site_domain": user.registration_site.domain if user.registration_site else None,
                "display_name": user.display_name,
                "country_code": user.country_code,
                "language_code": user.language_code,
                "is_anonymous": user.is_anonymous,
                "lifecycle_status": user.lifecycle_status,
                "has_phone": user.has_phone,
                "has_email": user.has_email,
                "has_whatsapp": user.has_whatsapp,
                "is_invited_user": user.is_invited_user,
                "is_new_user": user.is_new_user,
                "restrict_task_claim": user.restrict_task_claim,
                "registration_invite_code": user.registration_invite_code,
                "registration_ip": user.registration_ip,
                "last_active_at": user.last_active_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "identities": [
                    UserIdentityResponse.model_validate(
                        {
                            "identity_type": identity.identity_type,
                            "identity_value": identity.identity_value,
                            "country_code": identity.country_code,
                            "is_verified": identity.is_verified,
                            "is_primary": identity.is_primary,
                        }
                    )
                    for identity in user.identities
                ],
                "tags": tags,
            }
        )

    def _serialize_audience_rule(self, rule: AudienceRuleSet) -> AudienceRuleSetResponse:
        return AudienceRuleSetResponse.model_validate(
            {
                "id": rule.id,
                "rule_key": rule.rule_key,
                "name": rule.name,
                "scope_type": rule.scope_type,
                "scope_id": rule.scope_id,
                "status": rule.status,
                "description": rule.description,
                "rules_json": rule.rules_json,
                "created_by": rule.created_by,
                "updated_by": rule.updated_by,
                "created_at": rule.created_at,
                "updated_at": rule.updated_at,
            }
        )
