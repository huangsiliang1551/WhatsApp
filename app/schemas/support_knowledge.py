from datetime import datetime

from pydantic import BaseModel, Field


class SupportKnowledgeEntryView(BaseModel):
    account_id: str | None = None
    article_id: str
    route_name: str
    category: str
    title: str
    answer: str
    source_language: str
    keywords: list[str]
    minimum_score: int
    priority: int
    is_active: bool
    source_type: str


class SupportKnowledgeEntryCreateRequest(BaseModel):
    account_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    route_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    source_language: str = Field(default="en", min_length=2)
    keywords: list[str] = Field(default_factory=list)
    minimum_score: int = Field(default=1, ge=1)
    priority: int = Field(default=100, ge=0)
    is_active: bool = True


class SupportKnowledgeEntryUpdateRequest(BaseModel):
    route_name: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1)
    answer: str | None = Field(default=None, min_length=1)
    source_language: str | None = Field(default=None, min_length=2)
    keywords: list[str] | None = None
    minimum_score: int | None = Field(default=None, ge=1)
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class SupportKnowledgeExportBundle(BaseModel):
    version: str = "2026-06-06"
    exported_at: datetime
    total_entries: int
    entries: list[SupportKnowledgeEntryCreateRequest]


class SupportKnowledgeImportRequest(BaseModel):
    target_account_id: str | None = Field(default=None, min_length=1)
    upsert_existing: bool = True
    entries: list[SupportKnowledgeEntryCreateRequest] = Field(min_length=1)


class SupportKnowledgeImportItemResult(BaseModel):
    account_id: str
    article_id: str
    route_name: str
    status: str
    detail: str


class SupportKnowledgeImportResult(BaseModel):
    created_count: int
    updated_count: int
    skipped_count: int
    items: list[SupportKnowledgeImportItemResult]
