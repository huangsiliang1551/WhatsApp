"""Backup and restore API — IV-BE-001.

Endpoints:
  POST   /api/backups          — create backup
  GET    /api/backups           — list backups
  POST   /api/backups/{id}/restore — restore from backup
  DELETE /api/backups/{id}      — delete backup
  GET    /api/backups/{id}/download — download backup file
"""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.core.settings import Settings, get_settings
from app.services.backup_service import BackupService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.post("", summary="创建备份")
async def create_backup(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("backups.create")),
):
    svc = BackupService(session, settings)
    record = await svc.create_backup(user_id="admin", backup_type="manual")
    return {
        "id": record.id,
        "filename": record.filename,
        "status": record.status,
        "started_at": record.started_at.isoformat() if record.started_at else None,
    }


@router.get("", summary="列出备份")
def list_backups(
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("backups.view")),
):
    svc = BackupService(session)
    backups = svc.list_backups()
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "file_size": b.file_size,
            "backup_type": b.backup_type,
            "status": b.status,
            "started_at": b.started_at.isoformat() if b.started_at else None,
            "completed_at": b.completed_at.isoformat() if b.completed_at else None,
            "error_message": b.error_message,
        }
        for b in backups
    ]


@router.post("/{backup_id}/restore", summary="恢复备份")
async def restore_backup(
    backup_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _actor: RequestActor = Depends(require_permission("backups.restore")),
):
    svc = BackupService(session, settings)
    result = await svc.restore_backup(backup_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "恢复失败"))
    return result


@router.delete("/{backup_id}", summary="删除备份")
def delete_backup(
    backup_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("backups.delete")),
):
    svc = BackupService(session)
    if not svc.delete_backup(backup_id):
        raise HTTPException(status_code=404, detail="备份不存在")
    return {"success": True}


@router.get("/{backup_id}/download", summary="下载备份文件")
def download_backup(
    backup_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("backups.view")),
):
    svc = BackupService(session)
    record = svc.get_backup(backup_id)
    if not record:
        raise HTTPException(status_code=404, detail="备份不存在")
    if not record.file_path or not os.path.exists(record.file_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    return FileResponse(
        record.file_path,
        filename=record.filename,
        media_type="application/gzip",
    )
