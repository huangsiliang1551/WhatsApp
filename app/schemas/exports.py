from pydantic import BaseModel, Field


class ExportCreateRequest(BaseModel):
    type: str = Field(..., description="Export type: conversations, templates, tickets, customers, users, audit_logs")
    filters: dict | None = Field(default=None, description="Optional filters like account_id, status")
    format: str = Field(default="csv", description="Output format (only csv supported)")
    columns: list[str] | None = Field(default=None, description="Specific columns to include")
    account_id: str | None = Field(default=None, description="Account scope for the export")


class ExportCreateResponse(BaseModel):
    export_id: str
    status: str
    estimated_rows: int


class ExportStatusResponse(BaseModel):
    export_id: str
    status: str
    download_url: str | None = None
    file_size_bytes: int = 0
    row_count: int = 0
    expires_at: str | None = None
    error: str | None = None
