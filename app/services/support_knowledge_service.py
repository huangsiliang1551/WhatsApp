from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account, SupportKnowledgeEntry
from app.schemas.support_knowledge import (
    SupportKnowledgeExportBundle,
    SupportKnowledgeImportItemResult,
    SupportKnowledgeImportRequest,
    SupportKnowledgeImportResult,
    SupportKnowledgeEntryCreateRequest,
    SupportKnowledgeEntryUpdateRequest,
    SupportKnowledgeEntryView,
)
from app.services.knowledge_base import (
    SupportKnowledgeEntry as BuiltinSupportKnowledgeEntry,
    SupportKnowledgeMatch,
    list_support_knowledge,
    match_support_knowledge_entries,
    normalize_support_knowledge_text,
)


class SupportKnowledgeService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def list_entries(
        self,
        account_id: str | None = None,
        category: str | None = None,
        include_builtin: bool = True,
    ) -> list[SupportKnowledgeEntryView]:
        query = select(SupportKnowledgeEntry).order_by(
            SupportKnowledgeEntry.account_id,
            SupportKnowledgeEntry.priority,
            SupportKnowledgeEntry.title,
        )
        if account_id is not None:
            query = query.where(SupportKnowledgeEntry.account_id == account_id)
        if category is not None:
            query = query.where(SupportKnowledgeEntry.category == category)

        database_entries = [
            self._serialize_database_entry(entry)
            for entry in self._session.scalars(query).all()
        ]
        if not include_builtin:
            return database_entries

        builtin_entries = [
            SupportKnowledgeEntryView(
                account_id=None,
                article_id=entry.article_id,
                route_name=entry.route_name,
                category=entry.category,
                title=entry.title,
                answer=entry.answer,
                source_language="en",
                keywords=list(entry.keywords),
                minimum_score=entry.minimum_score,
                priority=100,
                is_active=True,
                source_type="builtin",
            )
            for entry in list_support_knowledge(category=category)
        ]
        return [*database_entries, *builtin_entries]

    async def create_entry(
        self,
        payload: SupportKnowledgeEntryCreateRequest,
    ) -> SupportKnowledgeEntryView:
        account = self._session.get(Account, payload.account_id)
        if account is None:
            raise LookupError(f"Account '{payload.account_id}' was not found.")

        existing_article = self._session.scalars(
            select(SupportKnowledgeEntry).where(
                SupportKnowledgeEntry.account_id == payload.account_id,
                SupportKnowledgeEntry.article_id == payload.article_id,
            )
        ).first()
        if existing_article is not None:
            raise ValueError(
                f"Support knowledge article '{payload.article_id}' already exists for account '{payload.account_id}'."
            )

        existing_route = self._session.scalars(
            select(SupportKnowledgeEntry).where(
                SupportKnowledgeEntry.account_id == payload.account_id,
                SupportKnowledgeEntry.route_name == payload.route_name,
            )
        ).first()
        if existing_route is not None:
            raise ValueError(
                f"Support knowledge route '{payload.route_name}' already exists for account '{payload.account_id}'."
            )

        entry = SupportKnowledgeEntry(
            account_id=payload.account_id,
            article_id=payload.article_id,
            route_name=payload.route_name,
            category=payload.category,
            title=payload.title,
            answer_text=payload.answer,
            source_language=payload.source_language,
            keywords_json=payload.keywords,
            minimum_score=payload.minimum_score,
            priority=payload.priority,
            is_active=payload.is_active,
        )
        self._session.add(entry)
        self._session.commit()
        self._session.refresh(entry)
        return self._serialize_database_entry(entry)

    async def update_entry(
        self,
        account_id: str,
        article_id: str,
        payload: SupportKnowledgeEntryUpdateRequest,
    ) -> SupportKnowledgeEntryView:
        entry = self._require_entry(account_id=account_id, article_id=article_id)

        if payload.route_name is not None and payload.route_name != entry.route_name:
            existing_route = self._session.scalars(
                select(SupportKnowledgeEntry).where(
                    SupportKnowledgeEntry.account_id == account_id,
                    SupportKnowledgeEntry.route_name == payload.route_name,
                )
            ).first()
            if existing_route is not None and existing_route.id != entry.id:
                raise ValueError(
                    f"Support knowledge route '{payload.route_name}' already exists for account '{account_id}'."
                )
            entry.route_name = payload.route_name

        if payload.category is not None:
            entry.category = payload.category
        if payload.title is not None:
            entry.title = payload.title
        if payload.answer is not None:
            entry.answer_text = payload.answer
        if payload.source_language is not None:
            entry.source_language = payload.source_language
        if payload.keywords is not None:
            entry.keywords_json = payload.keywords
        if payload.minimum_score is not None:
            entry.minimum_score = payload.minimum_score
        if payload.priority is not None:
            entry.priority = payload.priority
        if payload.is_active is not None:
            entry.is_active = payload.is_active

        self._session.add(entry)
        self._session.commit()
        self._session.refresh(entry)
        return self._serialize_database_entry(entry)

    async def delete_entry(self, account_id: str, article_id: str) -> None:
        entry = self._require_entry(account_id=account_id, article_id=article_id)
        self._session.delete(entry)
        self._session.commit()

    async def export_entries(
        self,
        account_id: str | None = None,
        category: str | None = None,
        include_inactive: bool = True,
    ) -> SupportKnowledgeExportBundle:
        query = select(SupportKnowledgeEntry).order_by(
            SupportKnowledgeEntry.account_id,
            SupportKnowledgeEntry.priority,
            SupportKnowledgeEntry.title,
        )
        if account_id is not None:
            query = query.where(SupportKnowledgeEntry.account_id == account_id)
        if category is not None:
            query = query.where(SupportKnowledgeEntry.category == category)
        if not include_inactive:
            query = query.where(SupportKnowledgeEntry.is_active.is_(True))

        entries = [
            SupportKnowledgeEntryCreateRequest(
                account_id=entry.account_id,
                article_id=entry.article_id,
                route_name=entry.route_name,
                category=entry.category,
                title=entry.title,
                answer=entry.answer_text,
                source_language=entry.source_language,
                keywords=list(entry.keywords_json or []),
                minimum_score=entry.minimum_score,
                priority=entry.priority,
                is_active=entry.is_active,
            )
            for entry in self._session.scalars(query).all()
        ]
        return SupportKnowledgeExportBundle(
            exported_at=datetime.now(UTC),
            total_entries=len(entries),
            entries=entries,
        )

    async def import_entries(
        self,
        payload: SupportKnowledgeImportRequest,
    ) -> SupportKnowledgeImportResult:
        if payload.target_account_id is not None:
            account = self._session.get(Account, payload.target_account_id)
            if account is None:
                raise LookupError(f"Account '{payload.target_account_id}' was not found.")

        items: list[SupportKnowledgeImportItemResult] = []
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for entry in payload.entries:
            effective_account_id = payload.target_account_id or entry.account_id
            effective_payload = SupportKnowledgeEntryCreateRequest(
                account_id=effective_account_id,
                article_id=entry.article_id,
                route_name=entry.route_name,
                category=entry.category,
                title=entry.title,
                answer=entry.answer,
                source_language=entry.source_language,
                keywords=entry.keywords,
                minimum_score=entry.minimum_score,
                priority=entry.priority,
                is_active=entry.is_active,
            )
            existing_article = self._session.scalars(
                select(SupportKnowledgeEntry).where(
                    SupportKnowledgeEntry.account_id == effective_account_id,
                    SupportKnowledgeEntry.article_id == entry.article_id,
                )
            ).first()

            try:
                if existing_article is None:
                    await self.create_entry(effective_payload)
                    created_count += 1
                    items.append(
                        SupportKnowledgeImportItemResult(
                            account_id=effective_account_id,
                            article_id=entry.article_id,
                            route_name=entry.route_name,
                            status="created",
                            detail="created",
                        )
                    )
                    continue

                if not payload.upsert_existing:
                    skipped_count += 1
                    items.append(
                        SupportKnowledgeImportItemResult(
                            account_id=effective_account_id,
                            article_id=entry.article_id,
                            route_name=entry.route_name,
                            status="skipped",
                            detail="article already exists and upsert is disabled",
                        )
                    )
                    continue

                await self.update_entry(
                    account_id=effective_account_id,
                    article_id=entry.article_id,
                    payload=SupportKnowledgeEntryUpdateRequest(
                        route_name=entry.route_name,
                        category=entry.category,
                        title=entry.title,
                        answer=entry.answer,
                        source_language=entry.source_language,
                        keywords=entry.keywords,
                        minimum_score=entry.minimum_score,
                        priority=entry.priority,
                        is_active=entry.is_active,
                    ),
                )
                updated_count += 1
                items.append(
                    SupportKnowledgeImportItemResult(
                        account_id=effective_account_id,
                        article_id=entry.article_id,
                        route_name=entry.route_name,
                        status="updated",
                        detail="updated",
                    )
                )
            except (LookupError, ValueError) as exc:
                skipped_count += 1
                items.append(
                    SupportKnowledgeImportItemResult(
                        account_id=effective_account_id,
                        article_id=entry.article_id,
                        route_name=entry.route_name,
                        status="skipped",
                        detail=str(exc),
                    )
                )

        return SupportKnowledgeImportResult(
            created_count=created_count,
            updated_count=updated_count,
            skipped_count=skipped_count,
            items=items,
        )

    async def match_entry(
        self,
        account_id: str,
        user_message: str,
    ) -> SupportKnowledgeMatch | None:
        query = (
            select(SupportKnowledgeEntry)
            .where(
                SupportKnowledgeEntry.account_id == account_id,
                SupportKnowledgeEntry.is_active.is_(True),
            )
            .order_by(SupportKnowledgeEntry.priority.asc(), SupportKnowledgeEntry.created_at.asc())
        )
        entries = [
            BuiltinSupportKnowledgeEntry(
                article_id=entry.article_id,
                route_name=entry.route_name,
                category=entry.category,
                title=entry.title,
                answer=entry.answer_text,
                keywords=tuple(entry.keywords_json or []),
                source_language=entry.source_language,
                minimum_score=entry.minimum_score,
            )
            for entry in self._session.scalars(query).all()
        ]
        if not entries:
            return None
        return match_support_knowledge_entries(
            entries=entries,
            normalized_text=normalize_support_knowledge_text(user_message),
        )

    def _require_entry(self, account_id: str, article_id: str) -> SupportKnowledgeEntry:
        entry = self._session.scalars(
            select(SupportKnowledgeEntry).where(
                SupportKnowledgeEntry.account_id == account_id,
                SupportKnowledgeEntry.article_id == article_id,
            )
        ).first()
        if entry is None:
            raise LookupError(
                f"Support knowledge article '{article_id}' for account '{account_id}' was not found."
            )
        return entry

    def _serialize_database_entry(self, entry: SupportKnowledgeEntry) -> SupportKnowledgeEntryView:
        return SupportKnowledgeEntryView(
            account_id=entry.account_id,
            article_id=entry.article_id,
            route_name=entry.route_name,
            category=entry.category,
            title=entry.title,
            answer=entry.answer_text,
            source_language=entry.source_language,
            keywords=list(entry.keywords_json or []),
            minimum_score=entry.minimum_score,
            priority=entry.priority,
            is_active=entry.is_active,
            source_type="database",
        )
