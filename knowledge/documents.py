"""Document registry + local/MinIO object storage."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from knowledge.models import DocumentMeta, new_id, utc_now
from knowledge.settings import KnowledgeSettings, get_settings

logger = logging.getLogger("researchos.knowledge.documents")


def content_hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class DocumentRegistry:
    """In-memory document metadata + object bytes (local dir or MinIO)."""

    def __init__(self, settings: KnowledgeSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._docs: dict[str, DocumentMeta] = {}
        self._minio = None
        if self.settings.minio_endpoint and self.settings.minio_access_key:
            try:
                from minio import Minio

                self._minio = Minio(
                    self.settings.minio_endpoint,
                    access_key=self.settings.minio_access_key,
                    secret_key=self.settings.minio_secret_key or "",
                    secure=self.settings.minio_secure,
                )
                bucket = self.settings.minio_bucket_documents
                if not self._minio.bucket_exists(bucket):
                    self._minio.make_bucket(bucket)
                logger.info("MinIO documents bucket ready: %s", bucket)
            except Exception as exc:  # noqa: BLE001
                logger.warning("MinIO unavailable (%s); using local objects dir", exc)
                self._minio = None
        self.settings.objects_path.mkdir(parents=True, exist_ok=True)

    def clear(self) -> None:
        self._docs.clear()

    def get(self, doc_id: str) -> DocumentMeta | None:
        return self._docs.get(doc_id)

    def list(self, workspace_id: str | None = None) -> list[DocumentMeta]:
        docs = list(self._docs.values())
        if workspace_id:
            docs = [d for d in docs if d.workspace_id == workspace_id]
        return docs

    def register(
        self,
        *,
        title: str | None = None,
        filename: str | None = None,
        mime_type: str | None = None,
        workspace_id: str | None = None,
        url: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        doc_id: str | None = None,
    ) -> DocumentMeta:
        ext = None
        if filename and "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
        meta = DocumentMeta(
            doc_id=doc_id or new_id("doc"),
            workspace_id=workspace_id or self.settings.default_workspace_id,
            title=title or filename,
            mime_type=mime_type,
            extension=ext,
            source_file=filename,
            url=url,
            tags=tags or [],
            metadata=metadata or {},
            status="registered",
        )
        self._docs[meta.doc_id] = meta
        return meta

    def put_bytes(
        self,
        doc_id: str,
        data: bytes,
        *,
        filename: str | None = None,
    ) -> DocumentMeta:
        meta = self._docs.get(doc_id)
        if meta is None:
            meta = self.register(filename=filename, doc_id=doc_id)
        meta.status = "storing"
        meta.content_hash = content_hash(data)
        ext = meta.extension or (
            filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else "bin"
        )
        object_key = f"{meta.workspace_id}/raw/{meta.doc_id}/original.{ext}"
        if self._minio is not None:
            from io import BytesIO

            self._minio.put_object(
                self.settings.minio_bucket_documents,
                object_key,
                BytesIO(data),
                length=len(data),
            )
        else:
            path = self.settings.objects_path / object_key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        meta.object_key = object_key
        meta.source_file = filename or meta.source_file
        meta.updated_at = utc_now()
        meta.status = "stored"
        self._docs[meta.doc_id] = meta
        return meta

    def read_bytes(self, doc_id: str) -> bytes:
        meta = self._docs.get(doc_id)
        if meta is None or not meta.object_key:
            raise FileNotFoundError(f"document not found: {doc_id}")
        if self._minio is not None:
            resp = self._minio.get_object(self.settings.minio_bucket_documents, meta.object_key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        path = self.settings.objects_path / meta.object_key
        return path.read_bytes()

    def update_status(self, doc_id: str, status: str, **fields: Any) -> DocumentMeta:
        meta = self._docs[doc_id]
        meta.status = status
        for k, v in fields.items():
            if hasattr(meta, k):
                setattr(meta, k, v)
            else:
                meta.metadata[k] = v
        meta.updated_at = utc_now()
        self._docs[doc_id] = meta
        return meta
