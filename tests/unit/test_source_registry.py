"""Unit tests for Source Registry Service and compliance state machine."""

import pytest

from database.session import SessionLocal
from packages.schemas.models import Source
from services.collectors.source_registry import SourceComplianceError, SourceRegistryService


def test_source_approval_and_activation_flow():
    """Verifies that an unapproved source cannot be activated until approved."""
    db = SessionLocal()
    try:
        source = Source(
            name="Test Review Source",
            type="OTA",
            access_method="PLAYWRIGHT",
            permission_status="REVIEW_REQUIRED",
            health_status="REVIEW_REQUIRED",
            enabled=False,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        # Unapproved source cannot collect
        assert SourceRegistryService.can_collect(source) is False

        # Attempting direct activation without approval must fail
        with pytest.raises(SourceComplianceError):
            SourceRegistryService.transition_state(db, source.id, "ACTIVE")

        # Approve source
        SourceRegistryService.approve_source(db, source.id)
        db.refresh(source)
        assert source.permission_status == "APPROVED"
        assert source.health_status == "APPROVED"

        # Now transition to ACTIVE is permitted
        SourceRegistryService.transition_state(db, source.id, "ACTIVE")
        db.refresh(source)
        assert source.health_status == "ACTIVE"
        assert source.enabled is True
        assert SourceRegistryService.can_collect(source) is True

    finally:
        # Cleanup
        db.query(Source).filter(Source.name == "Test Review Source").delete()
        db.commit()
        db.close()


def test_illegal_state_transition():
    """Illegal transitions (e.g. DISCOVERED directly to ACTIVE) raise SourceComplianceError."""
    db = SessionLocal()
    try:
        source = Source(
            name="Test Discovered Source",
            type="OTA",
            access_method="PLAYWRIGHT",
            permission_status="REVIEW_REQUIRED",
            health_status="DISCOVERED",
            enabled=False,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        with pytest.raises(SourceComplianceError) as exc:
            SourceRegistryService.transition_state(db, source.id, "ACTIVE")
        assert "Illegal state transition" in str(exc.value)

    finally:
        db.query(Source).filter(Source.name == "Test Discovered Source").delete()
        db.commit()
        db.close()
