"""Knowledge base API — IV-BE-003.

Endpoints:
  GET    /api/knowledge/categories          — list categories
  POST   /api/knowledge/categories          — create category
  PATCH  /api/knowledge/categories/{id}     — update category
  DELETE /api/knowledge/categories/{id}     — delete category
  GET    /api/knowledge/articles            — list articles (with search)
  POST   /api/knowledge/articles            — create article
  PATCH  /api/knowledge/articles/{id}       — update article
  DELETE /api/knowledge/articles/{id}       — delete article
  GET    /api/knowledge/search              — search articles
  POST   /api/knowledge/ai-answer           — AI answer from KB
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class CreateCategoryRequest(BaseModel):
    name: str
    description: str | None = None
    sort_order: int = 0


class UpdateCategoryRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None


class CreateArticleRequest(BaseModel):
    title: str
    content: str
    category_id: str | None = None
    keywords: str | None = None
    is_published: bool = True


class UpdateArticleRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category_id: str | None = None
    keywords: str | None = None
    is_published: bool | None = None


class AiAnswerRequest(BaseModel):
    question: str


# ─── Categories ─────────────────────────────────────────────────────────────


@router.get("/categories", summary="分类列表")
def list_categories(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.view")),
):
    svc = KnowledgeBaseService(session)
    cats = svc.list_categories()
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "sort_order": c.sort_order,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cats
    ]


@router.post("/categories", summary="创建分类", status_code=201)
def create_category(
    body: CreateCategoryRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.manage")),
):
    svc = KnowledgeBaseService(session)
    cat = svc.create_category(name=body.name, description=body.description, sort_order=body.sort_order)
    return {
        "id": cat.id,
        "name": cat.name,
        "description": cat.description,
        "sort_order": cat.sort_order,
    }


@router.patch("/categories/{category_id}", summary="编辑分类")
def update_category(
    category_id: str,
    body: UpdateCategoryRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.manage")),
):
    svc = KnowledgeBaseService(session)
    cat = svc.update_category(
        category_id=category_id,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
    )
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {
        "id": cat.id,
        "name": cat.name,
        "description": cat.description,
        "sort_order": cat.sort_order,
    }


@router.delete("/categories/{category_id}", summary="删除分类")
def delete_category(
    category_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.manage")),
):
    svc = KnowledgeBaseService(session)
    if not svc.delete_category(category_id):
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"success": True}


# ─── Articles ───────────────────────────────────────────────────────────────


@router.get("/articles", summary="文章列表")
def list_articles(
    category_id: str | None = Query(None),
    search: str | None = Query(None),
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.view")),
):
    svc = KnowledgeBaseService(session)
    articles = svc.list_articles(category_id=category_id, search=search, published_only=False)
    return [
        {
            "id": a.id,
            "title": a.title,
            "category_id": a.category_id,
            "keywords": a.keywords,
            "is_published": a.is_published,
            "view_count": a.view_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        for a in articles
    ]


@router.post("/articles", summary="创建文章", status_code=201)
def create_article(
    body: CreateArticleRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.manage")),
):
    svc = KnowledgeBaseService(session)
    art = svc.create_article(
        title=body.title,
        content=body.content,
        category_id=body.category_id,
        keywords=body.keywords,
        is_published=body.is_published,
    )
    return {
        "id": art.id,
        "title": art.title,
        "category_id": art.category_id,
        "is_published": art.is_published,
    }


@router.patch("/articles/{article_id}", summary="编辑文章")
def update_article(
    article_id: str,
    body: UpdateArticleRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.manage")),
):
    svc = KnowledgeBaseService(session)
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    art = svc.update_article(article_id, **kwargs)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    return {
        "id": art.id,
        "title": art.title,
        "category_id": art.category_id,
        "is_published": art.is_published,
    }


@router.delete("/articles/{article_id}", summary="删除文章")
def delete_article(
    article_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.manage")),
):
    svc = KnowledgeBaseService(session)
    if not svc.delete_article(article_id):
        raise HTTPException(status_code=404, detail="文章不存在")
    return {"success": True}


# ─── Search & AI ────────────────────────────────────────────────────────────


@router.get("/search", summary="搜索文章")
def search_articles(
    q: str = Query(..., description="搜索关键词"),
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.view")),
):
    svc = KnowledgeBaseService(session)
    return svc.search(query=q)


@router.post("/ai-answer", summary="AI 回答")
async def ai_answer(
    body: AiAnswerRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("knowledge.view")),
):
    from app.providers.factory import get_ai_provider
    from app.core.settings import get_settings

    settings = get_settings()
    provider = get_ai_provider(settings)
    svc = KnowledgeBaseService(session, ai_provider=provider)
    answer = svc.get_ai_answer(question=body.question)
    return {
        "question": body.question,
        "answer": answer,
        "has_answer": answer is not None,
    }
