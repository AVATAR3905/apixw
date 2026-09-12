"""Immutable raw payload storage with SHA-256 cryptographic hashing (PRD Section 18, 40.5, 78)."""

import datetime
import hashlib
import json
import os
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from packages.schemas.models import RawPayload


class PayloadIntegrityError(Exception):
    """Raised when cryptographic hash verification fails upon retrieval."""

    pass


class PayloadStore:
    """Manages immutable file-based storage and tamper-evident SHA-256 verification of raw collector payloads."""

    BASE_DATA_DIR = "data/raw"

    @classmethod
    def compute_hash(cls, content: Union[str, bytes]) -> str:
        """Computes SHA-256 hex digest of raw payload content."""
        if isinstance(content, str):
            payload_bytes = content.encode("utf-8")
        else:
            payload_bytes = content
        return hashlib.sha256(payload_bytes).hexdigest()

    @classmethod
    def store_payload(
        cls,
        db: Session,
        source_id: int,
        content: Union[str, bytes, Dict[str, Any]],
        content_type: str = "application/json",
        collection_job_id: Optional[int] = None,
        now: Optional[datetime.datetime] = None,
    ) -> RawPayload:
        """
        Stores payload to immutable disk structure and records hash in database.
        Path: data/raw/YYYY/MM/DD/{sha256_hash}.json
        """
        if now is None:
            now = datetime.datetime.now(datetime.UTC)

        # Standardize content to bytes and string for disk
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, indent=2, sort_keys=True)
            content_bytes = content_str.encode("utf-8")
            ext = ".json"
        elif isinstance(content, str):
            content_str = content
            content_bytes = content.encode("utf-8")
            ext = ".html" if "html" in content_type.lower() else ".json"
        else:
            content_bytes = content
            content_str = None
            ext = ".bin"

        # Compute SHA-256
        sha256_hash = cls.compute_hash(content_bytes)

        # Build directory structure
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")

        target_dir = os.path.join(cls.BASE_DATA_DIR, year, month, day)
        os.makedirs(target_dir, exist_ok=True)

        file_path = os.path.join(target_dir, f"{sha256_hash}{ext}")

        # Write to disk if not already present (immutable storage)
        if not os.path.exists(file_path):
            if content_str is not None:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content_str)
            else:
                with open(file_path, "wb") as f:
                    f.write(content_bytes)

        # Record in database
        payload_record = RawPayload(
            source_id=source_id,
            collection_job_id=collection_job_id,
            payload_uri=file_path.replace("\\", "/"),
            payload_hash=sha256_hash,
            content_type=content_type,
            captured_at=now,
        )
        db.add(payload_record)
        db.commit()
        db.refresh(payload_record)

        return payload_record

    @classmethod
    def retrieve_payload(cls, db: Session, payload_id: int) -> str:
        """
        Retrieves raw payload from disk and verifies SHA-256 integrity.
        Raises PayloadIntegrityError if payload has been modified or corrupted.
        """
        record = db.query(RawPayload).filter(RawPayload.id == payload_id).first()
        if not record:
            raise FileNotFoundError(f"Raw payload record {payload_id} not found in database")

        file_path = record.payload_uri
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Payload file missing from disk: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Cryptographic verification
        actual_hash = cls.compute_hash(content)
        if actual_hash != record.payload_hash:
            raise PayloadIntegrityError(
                f"Tamper detected! Expected hash {record.payload_hash} but found {actual_hash} on disk."
            )

        return content
