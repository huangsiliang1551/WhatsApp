"""Template package upload, extraction and manifest management service."""
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.db.models import H5Template

logger = structlog.get_logger()

UPLOAD_DIR = "/opt/whatsapp/uploads/templates"
EXTRACT_DIR = "/opt/whatsapp/static/templates"
MAX_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {".zip", ".rar"}


class TemplatePackageService:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def upload_package(self, template_id: str, file: UploadFile) -> dict:
        """Upload a template package (ZIP/RAR), extract and validate."""
        return await self._store_package(template_id, file, preserve_existing=False)

    async def replace_package(self, template_id: str, file: UploadFile) -> dict:
        """Replace an existing template package without losing the last good build on failure."""
        return await self._store_package(template_id, file, preserve_existing=True)

    async def _store_package(
        self,
        template_id: str,
        file: UploadFile,
        *,
        preserve_existing: bool,
    ) -> dict:
        """Save a package, validate it in a temp directory, then atomically promote it."""
        filename = file.filename or ""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_SIZE // (1024*1024)}MB")

        template = self._session.get(H5Template, template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")

        upload_dir = Path(UPLOAD_DIR) / template_id
        extract_dir = Path(EXTRACT_DIR) / template_id
        temp_extract_dir = Path(EXTRACT_DIR) / f"{template_id}.tmp-{uuid4().hex}"
        backup_extract_dir = Path(EXTRACT_DIR) / f"{template_id}.bak-{uuid4().hex}"
        upload_dir.mkdir(parents=True, exist_ok=True)
        temp_extract_dir.mkdir(parents=True, exist_ok=True)

        package_path = upload_dir / filename
        package_path.write_bytes(content)

        try:
            self._extract_package(package_path, temp_extract_dir, ext)
            manifest = self._validate_extracted(temp_extract_dir)
        except Exception as exc:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
            if not preserve_existing or not template.preview_path:
                template.status = "error"
            self._session.flush()
            raise HTTPException(status_code=400, detail=f"Extraction failed: {str(exc)}")

        try:
            if extract_dir.exists():
                shutil.move(str(extract_dir), str(backup_extract_dir))
            shutil.move(str(temp_extract_dir), str(extract_dir))
            shutil.rmtree(backup_extract_dir, ignore_errors=True)
        except Exception as exc:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
            if backup_extract_dir.exists() and not extract_dir.exists():
                shutil.move(str(backup_extract_dir), str(extract_dir))
            raise HTTPException(status_code=500, detail=f"Failed to finalize package: {str(exc)}")

        template.package_filename = filename
        template.package_size = len(content)
        template.package_uploaded_at = datetime.now(timezone.utc)
        template.preview_path = f"/templates/{template_id}/index.html"
        template.preview_url = template.preview_path
        template.status = "ready"
        self._session.flush()

        return {
            "id": template.id,
            "name": template.name,
            "preview_url": template.preview_path,
            "preview_path": template.preview_path,
            "manifest": manifest,
            "package_filename": filename,
            "package_size": len(content),
            "status": "ready",
            "package_uploaded_at": (
                template.package_uploaded_at.isoformat() if template.package_uploaded_at else None
            ),
        }

    def get_template_manifest(self, template_id: str) -> dict:
        """Read and return the manifest.json for a template."""
        manifest_path = Path(EXTRACT_DIR) / template_id / "manifest.json"
        if not manifest_path.exists():
            raise HTTPException(status_code=404, detail="Manifest not found. Upload package first.")
        try:
            with open(manifest_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid manifest.json: {e}")

    def list_available_templates(self) -> list[dict]:
        """List all templates with uploaded packages (including manifest data)."""
        templates = self._session.query(H5Template).filter(H5Template.status == "ready").all()
        results = []
        for t in templates:
            manifest = {}
            try:
                manifest = self.get_template_manifest(t.id)
            except (HTTPException, Exception):
                manifest = {"error": "cannot read manifest"}
            results.append({
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "status": t.status,
                "package_filename": t.package_filename,
                "package_size": t.package_size,
                "preview_path": t.preview_path,
                "manifest": manifest,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })
        return results

    def get_download_spec(self) -> str:
        """Return the template development specification as plain text."""
        return """# H5 模板开发规范

## 模板包结构
template-package.zip/
├── manifest.json         # 必选：模板元数据
├── index.html            # 必选：入口页面
├── assets/               # 可选：静态资源
│   ├── css/
│   ├── js/
│   └── images/
└── pages/                # 可选：子页面

## manifest.json 格式
{
  "name": "模板名称",
  "version": "1.0.0",
  "description": "模板描述",
  "author": "开发者",
  "entry": "index.html",
  "pages": ["index", "about", "contact"],
  "languages": ["zh-CN", "en"],
  "default_language": "zh-CN",
  "theme": {
    "primary_color": "#1677ff",
    "font_family": "sans-serif"
  }
}

## 约束
1. 包体 ≤ 100MB
2. 禁止路径穿越（../）
3. index.html 必须是有效的 HTML5 文档
4. 所有资源路径使用相对路径
5. 模板 JS 启动时调用 GET /api/h5/sites/{site_key}/brand-config
"""

    # ── Private helpers ──

    def _extract_package(self, package_path: Path, extract_dir: Path, ext: str) -> None:
        """Extract ZIP or RAR to extract_dir with path traversal protection."""
        if ext == ".zip":
            with zipfile.ZipFile(package_path, "r") as zf:
                for info in zf.infolist():
                    # Path traversal check
                    dest_path = self._safe_extract_path(extract_dir, info.filename)
                    if info.is_dir():
                        dest_path.mkdir(parents=True, exist_ok=True)
                    else:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(info.filename) as src, open(dest_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
        elif ext == ".rar":
            self._extract_rar(package_path, extract_dir)

    def _safe_extract_path(self, extract_dir: Path, member_path: str) -> Path:
        """Prevent path traversal by ensuring the resolved path is within extract_dir."""
        full_path = (extract_dir / member_path).resolve()
        extract_resolved = extract_dir.resolve()
        if not str(full_path).startswith(str(extract_resolved)):
            raise PermissionError(f"Path traversal detected: {member_path}")
        return full_path

    def _validate_extracted(self, extract_dir: Path) -> dict:
        """Validate that manifest.json and index.html exist in the extracted directory."""
        manifest_path = extract_dir / "manifest.json"
        index_path = extract_dir / "index.html"

        if not manifest_path.exists():
            raise FileNotFoundError("manifest.json is missing from the template package")
        if not index_path.exists():
            raise FileNotFoundError("index.html is missing from the template package")

        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid manifest.json: {e}")

        if not isinstance(manifest, dict):
            raise ValueError("manifest.json must be a JSON object")

        return manifest

    def _extract_rar(self, package_path: Path, extract_dir: Path) -> None:
        """Extract RAR archive using subprocess unar command."""
        import subprocess
        result = subprocess.run(
            ["unar", "-o", str(extract_dir), "-q", str(package_path)],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"RAR extraction failed: {result.stderr}")
