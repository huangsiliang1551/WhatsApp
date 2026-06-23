from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class TaskProofUploadRequest:
    task_instance_id: str
    site_id: str | None
    user_id: str
    original_filename: str
    content_type: str
    content: bytes


@dataclass(slots=True)
class TaskProofUploadResult:
    storage_provider: str
    object_key: str
    size_bytes: int
    sha256: str


@dataclass(slots=True)
class TaskProofUpload:
    file_name: str
    content_type: str
    file_bytes: bytes


@dataclass(slots=True)
class StoredTaskProof:
    proof_id: str
    file_name: str
    content_type: str
    file_size: int
    storage_key: str
    download_url: str | None


class TaskProofStorageProvider(ABC):
    provider_name: str

    @abstractmethod
    async def store_upload(self, payload: TaskProofUploadRequest) -> TaskProofUploadResult:
        raise NotImplementedError

    @abstractmethod
    async def build_read_url(self, object_key: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def delete_object(self, object_key: str) -> None:
        raise NotImplementedError
