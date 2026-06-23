"""Knowledge base service — IV-BE-003.

Manages knowledge categories and articles with keyword + semantic search,
and AI-powered answer generation from matched articles.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeArticle, KnowledgeCategory
from app.providers.ai.base import AIProvider

logger = structlog.get_logger()


class KnowledgeBaseService:
    """Knowledge base CRUD and search."""

    def __init__(self, session: Session, ai_provider: AIProvider | None = None) -> None:
        self._session = session
        self._ai_provider = ai_provider

    # ── Categories ────────────────────────────────────────────────────────────────

    def list_categories(self, agency_id: str | None = None) -> list[KnowledgeCategory]:
        stmt = select(KnowledgeCategory).order_by(KnowledgeCategory.sort_order)
        if agency_id:
            stmt = stmt.where(
                or_(KnowledgeCategory.agency_id == agency_id, KnowledgeCategory.agency_id.is_(None))
            )
        return list(self._session.scalars(stmt).all())

    def create_category(
        self,
        name: str,
        description: str | None = None,
        sort_order: int = 0,
        agency_id: str | None = None,
    ) -> KnowledgeCategory:
        cat = KnowledgeCategory(
            name=name,
            description=description,
            sort_order=sort_order,
            agency_id=agency_id,
        )
        self._session.add(cat)
        self._session.flush()
        return cat

    def update_category(
        self,
        category_id: str,
        name: str | None = None,
        description: str | None = None,
        sort_order: int | None = None,
    ) -> KnowledgeCategory | None:
        cat = self._session.get(KnowledgeCategory, category_id)
        if not cat:
            return None
        if name is not None:
            cat.name = name
        if description is not None:
            cat.description = description
        if sort_order is not None:
            cat.sort_order = sort_order
        return cat

    def delete_category(self, category_id: str) -> bool:
        cat = self._session.get(KnowledgeCategory, category_id)
        if not cat:
            return False
        # Unlink articles
        stmt = (
            select(KnowledgeArticle)
            .where(KnowledgeArticle.category_id == category_id)
        )
        articles = self._session.scalars(stmt).all()
        for art in articles:
            art.category_id = None
        self._session.delete(cat)
        return True

    # ── Articles ──────────────────────────────────────────────────────────────────

    def list_articles(
        self,
        category_id: str | None = None,
        agency_id: str | None = None,
        search: str | None = None,
        published_only: bool = True,
    ) -> list[KnowledgeArticle]:
        stmt = select(KnowledgeArticle)

        if published_only:
            stmt = stmt.where(KnowledgeArticle.is_published.is_(True))
        if category_id:
            stmt = stmt.where(KnowledgeArticle.category_id == category_id)
        if agency_id:
            stmt = stmt.where(
                or_(KnowledgeArticle.agency_id == agency_id, KnowledgeArticle.agency_id.is_(None))
            )
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                or_(
                    KnowledgeArticle.title.ilike(like),
                    KnowledgeArticle.content.ilike(like),
                    KnowledgeArticle.keywords.ilike(like),
                )
            )
        stmt = stmt.order_by(KnowledgeArticle.created_at.desc())
        return list(self._session.scalars(stmt).all())

    def create_article(
        self,
        title: str,
        content: str,
        category_id: str | None = None,
        agency_id: str | None = None,
        keywords: str | None = None,
        is_published: bool = True,
    ) -> KnowledgeArticle:
        article = KnowledgeArticle(
            title=title,
            content=content,
            category_id=category_id,
            agency_id=agency_id,
            keywords=keywords,
            is_published=is_published,
        )
        self._session.add(article)
        self._session.flush()
        return article

    def update_article(
        self,
        article_id: str,
        **kwargs: Any,
    ) -> KnowledgeArticle | None:
        article = self._session.get(KnowledgeArticle, article_id)
        if not article:
            return None
        for key, value in kwargs.items():
            if hasattr(article, key) and value is not None:
                setattr(article, key, value)
        return article

    def delete_article(self, article_id: str) -> bool:
        article = self._session.get(KnowledgeArticle, article_id)
        if not article:
            return False
        self._session.delete(article)
        return True

    def increment_view_count(self, article_id: str) -> None:
        self._session.execute(
            KnowledgeArticle.__table__.update()
            .where(KnowledgeArticle.id == article_id)
            .values(view_count=KnowledgeArticle.view_count + 1)
        )

    # ── Search ────────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        agency_id: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Keyword + semantic search.

        1. Keyword match: title / content / keywords LIKE query.
        2. If AI provider available, re-rank top matches by semantic relevance.
        3. Return deduplicated, sorted results.
        """
        like = f"%{query}%"
        stmt = (
            select(KnowledgeArticle)
            .where(
                KnowledgeArticle.is_published.is_(True),
                or_(
                    KnowledgeArticle.title.ilike(like),
                    KnowledgeArticle.content.ilike(like),
                    KnowledgeArticle.keywords.ilike(like),
                ),
            )
        )
        if agency_id:
            stmt = stmt.where(
                or_(KnowledgeArticle.agency_id == agency_id, KnowledgeArticle.agency_id.is_(None))
            )
        stmt = stmt.limit(top_k * 2)
        articles = list(self._session.scalars(stmt).all())

        results = []
        for a in articles:
            results.append({
                "id": a.id,
                "title": a.title,
                "content": a.content[:500],
                "keywords": a.keywords or "",
                "category_id": a.category_id,
                "view_count": a.view_count,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            })

        # Re-rank by semantic relevance if AI provider is available
        if self._ai_provider and results:
            try:
                results = self._semantic_rerank(query, results)
            except Exception:
                logger.warning("semantic_rerank_failed", exc_info=True)

        return results[:top_k]

    def _semantic_rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Use AI to re-rank results by relevance."""
        if not self._ai_provider:
            return results
        texts = [r["title"] + ": " + r["content"][:200] for r in results]
        prompt = (
            f"Query: {query}\n\n"
            f"Candidate articles:\n"
        )
        for i, t in enumerate(texts):
            prompt += f"{i}: {t}\n"
        prompt += "\nReturn the indices of top 3 most relevant articles, comma-separated. Only return indices."

        try:
            resp = self._ai_provider.generate_text(prompt)
            import re
            indices = re.findall(r"\d+", resp or "")
            scored = [int(i) for i in indices if 0 <= int(i) < len(results)]
            # Move scored results to top, preserve original order otherwise
            seen = set(scored)
            reranked = [results[i] for i in scored] + [r for i, r in enumerate(results) if i not in seen]
            return reranked
        except Exception:
            return results

    # ── AI Answer ─────────────────────────────────────────────────────────────────

    def get_ai_answer(
        self,
        question: str,
        agency_id: str | None = None,
    ) -> str | None:
        """Use AI to answer a question from knowledge base context."""
        if not self._ai_provider:
            logger.warning("ai_answer_skipped_no_provider")
            return None

        articles = self.search(question, agency_id, top_k=3)
        if not articles:
            return None

        context = "\n---\n".join(
            f"标题: {a['title']}\n内容: {a['content']}" for a in articles
        )
        prompt = (
            "你是一个客服知识库助手。请根据以下知识库内容回答用户问题。\n"
            "如果知识库内容不足以回答问题，请如实告知。\n\n"
            f"知识库内容：\n{context}\n\n"
            f"用户问题：{question}"
        )
        try:
            answer = self._ai_provider.generate_text(prompt)
            return answer
        except Exception as exc:
            logger.error("ai_answer_failed", error=str(exc))
            return None
