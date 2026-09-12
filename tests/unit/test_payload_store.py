"""Unit tests for immutable PayloadStore and SHA-256 cryptographic verification."""

import os

import pytest

from database.session import SessionLocal
from packages.schemas.models import RawPayload
from services.collectors.payload_store import PayloadIntegrityError, PayloadStore


def test_payload_storage_and_sha256_verification():
    """Stores payload, verifies SHA-256 hash match, and checks disk immutability."""
    db = SessionLocal()
    try:
        sample_json = {"flight": "6E-204", "fare": 4500.0, "route": "DEL-BOM"}
        payload_rec = PayloadStore.store_payload(
            db=db, source_id=1, content=sample_json, content_type="application/json"
        )

        assert payload_rec.id is not None
        assert len(payload_rec.payload_hash) == 64  # SHA-256 length
        assert os.path.exists(payload_rec.payload_uri)

        # Retrieve and verify
        retrieved_content = PayloadStore.retrieve_payload(db, payload_rec.id)
        assert "6E-204" in retrieved_content

    finally:
        db.close()


def test_payload_tamper_detection():
    """Modifying raw payload on disk triggers PayloadIntegrityError on retrieval."""
    db = SessionLocal()
    try:
        sample_text = "ORIGINAL_COMPLIANT_DATA"
        payload_rec = PayloadStore.store_payload(
            db=db, source_id=1, content=sample_text, content_type="text/plain"
        )

        # Simulate unauthorized file tampering on disk
        with open(payload_rec.payload_uri, "w", encoding="utf-8") as f:
            f.write("TAMPERED_MALICIOUS_DATA")

        # Retrieval must fail with cryptographic integrity error
        with pytest.raises(PayloadIntegrityError) as exc:
            PayloadStore.retrieve_payload(db, payload_rec.id)
        assert "Tamper detected" in str(exc.value)

    finally:
        # Cleanup
        if os.path.exists(payload_rec.payload_uri):
            os.remove(payload_rec.payload_uri)
        db.query(RawPayload).filter(RawPayload.id == payload_rec.id).delete()
        db.commit()
        db.close()
