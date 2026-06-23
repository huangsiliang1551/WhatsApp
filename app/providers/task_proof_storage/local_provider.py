from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.providers.task_proof_storage.base import (
    TaskProofStorageProvider,
    TaskProofUploadRequest,
    TaskProofUploadResult,
)


class LocalTaskProofStorageProvider(TaskProofStorageProvider):
    provider_name = "local"

    def __init__(self, root: str) -> None:
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    async def store_upload(self, payload: TaskProofUploadRequest) -> TaskProofUploadResult:
        extension = Path(payload.original_filename).suffix
        object_key = f"{payload.task_instance_id}/{uuid4().hex}{extension}"
        target_path = self._root / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload.content)
        return TaskProofUploadResult(
            storage_provider=self.provider_name,
            object_key=object_key,
            size_bytes=len(payload.content),
            sha256=sha256(payload.content).hexdigest(),
        )

    async def build_read_url(self, object_key: str) -> str:
        return str((self._root / object_key).resolve())

    async def delete_object(self, object_key: str) -> None:
        target_path = self._root / object_key
        if target_path.exists():
            target_path.unlink()
