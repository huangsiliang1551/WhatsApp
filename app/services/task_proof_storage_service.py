from sqlalchemy.orm import Session

from app.db.models import AppUser, H5Site, TaskInstance, TaskProofFile
from app.providers.task_proof_storage.base import (
    TaskProofStorageProvider,
    TaskProofUploadRequest,
)
from app.schemas.task_workflow import TaskProofFileResponse


class TaskProofStorageService:
    def __init__(
        self,
        *,
        session: Session,
        provider: TaskProofStorageProvider,
    ) -> None:
        self._session = session
        self._provider = provider

    async def upload_proof(
        self,
        *,
        task_instance_id: str,
        public_user_id: str,
        site_id: str | None,
        site_key: str | None,
        original_filename: str,
        content_type: str,
        content: bytes,
    ) -> TaskProofFileResponse:
        instance = self._require_task_instance(task_instance_id)
        user = self._require_submitter(instance, public_user_id)
        self._ensure_site_matches(instance=instance, site_id=site_id, site_key=site_key)
        upload_result = await self._provider.store_upload(
            TaskProofUploadRequest(
                task_instance_id=task_instance_id,
                site_id=instance.site_id,
                user_id=user.id,
                original_filename=original_filename,
                content_type=content_type,
                content=content,
            )
        )
        proof = TaskProofFile(
            account_id=instance.account_id,
            task_instance_id=instance.id,
            user_id=user.id,
            site_id=instance.site_id,
            storage_provider=upload_result.storage_provider,
            object_key=upload_result.object_key,
            original_filename=original_filename,
            mime_type=content_type,
            size_bytes=upload_result.size_bytes,
            sha256=upload_result.sha256,
            status="uploaded",
            uploaded_by_type="user",
            metadata_json=None,
        )
        self._session.add(proof)
        self._session.commit()
        self._session.refresh(proof)
        return await self.serialize_proof(proof)

    async def serialize_proof(self, proof: TaskProofFile) -> TaskProofFileResponse:
        return TaskProofFileResponse(
            id=proof.id,
            account_id=proof.account_id,
            task_instance_id=proof.task_instance_id,
            user_id=proof.user_id,
            site_id=proof.site_id,
            storage_provider=proof.storage_provider,
            object_key=proof.object_key,
            read_url=await self._provider.build_read_url(proof.object_key),
            original_filename=proof.original_filename,
            mime_type=proof.mime_type,
            size_bytes=proof.size_bytes,
            sha256=proof.sha256,
            status=proof.status,
            uploaded_by_type=proof.uploaded_by_type,
            created_at=proof.created_at,
        )

    def require_proofs(
        self,
        *,
        task_instance: TaskInstance,
        user: AppUser,
        proof_file_ids: list[str],
    ) -> list[TaskProofFile]:
        proofs: list[TaskProofFile] = []
        for proof_file_id in proof_file_ids:
            proof = self._session.get(TaskProofFile, proof_file_id)
            if proof is None:
                raise LookupError(f"Task proof file '{proof_file_id}' was not found.")
            if proof.task_instance_id != task_instance.id or proof.user_id != user.id:
                raise PermissionError(
                    f"Task proof file '{proof_file_id}' does not belong to task instance '{task_instance.id}'."
                )
            proofs.append(proof)
        return proofs

    def _require_task_instance(self, task_instance_id: str) -> TaskInstance:
        instance = self._session.get(TaskInstance, task_instance_id)
        if instance is None:
            raise LookupError(f"Task instance '{task_instance_id}' was not found.")
        return instance

    def _require_submitter(self, instance: TaskInstance, public_user_id: str) -> AppUser:
        user = self._session.get(AppUser, instance.user_id)
        if user is None or user.public_user_id != public_user_id:
            raise PermissionError(
                f"Task instance '{instance.id}' does not belong to public user '{public_user_id}'."
            )
        return user

    def _ensure_site_matches(
        self,
        *,
        instance: TaskInstance,
        site_id: str | None,
        site_key: str | None,
    ) -> None:
        if site_id is not None and instance.site_id != site_id:
            raise PermissionError(f"Task instance '{instance.id}' does not belong to site '{site_id}'.")
        if site_key is not None:
            site = self._session.get(H5Site, instance.site_id) if instance.site_id is not None else None
            resolved_site_key = site.site_key if site is not None else None
            if resolved_site_key != site_key:
                raise PermissionError(f"Task instance '{instance.id}' does not belong to site '{site_key}'.")
