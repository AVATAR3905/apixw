"""Unit tests for the source access-policy gate."""

import pytest

from database.seeds.seed_routes_airlines import seed_sources
from database.session import SessionLocal, init_db
from packages.schemas.models import Source
from services.collectors.source_registry import SourceRegistryService


def _approved_source(access_mode="PUBLIC", license_status="NOT_REQUIRED"):
    return Source(
        name="Access Mode Test Source",
        type="OTA",
        access_method="PLAYWRIGHT",
        access_mode=access_mode,
        permission_status="APPROVED",
        license_status=license_status,
        health_status="ACTIVE",
        enabled=True,
    )


def test_public_mode_needs_no_license():
    assert SourceRegistryService.can_collect(_approved_source("PUBLIC")) is True


def test_conditional_mode_requires_limited_use_license():
    assert (
        SourceRegistryService.can_collect(_approved_source("CONDITIONAL", "RESEARCH_EXEMPTION"))
        is True
    )
    assert (
        SourceRegistryService.can_collect(_approved_source("CONDITIONAL", "NOT_REQUIRED")) is False
    )


def test_partner_only_requires_partner_agreement():
    assert (
        SourceRegistryService.can_collect(_approved_source("PARTNER_ONLY", "PARTNER_AGREEMENT"))
        is True
    )
    assert (
        SourceRegistryService.can_collect(_approved_source("PARTNER_ONLY", "VALIDATOR_FALLBACK"))
        is False
    )


def test_blocked_reason_is_informative():
    src = _approved_source("PARTNER_ONLY", "VALIDATOR_FALLBACK")
    reason = SourceRegistryService._blocked_reason(src)
    assert "PARTNER_AGREEMENT" in reason

    disabled = _approved_source("PUBLIC")
    disabled.enabled = False
    assert "disabled" in SourceRegistryService._blocked_reason(disabled)


def test_seeded_rpc_source_is_blocked_until_partner_license():
    """Google Flights RPC source is seeded as PARTNER_ONLY and must not be collectable."""
    init_db()  # additive migration in case the DB predates access_mode
    db = SessionLocal()
    try:
        seed_sources(db)
        db.commit()
        src = (
            db.query(Source)
            .filter(Source.name == "Google Flights RPC Validator & Fallback")
            .first()
        )
        assert src is not None
        assert src.access_mode == "PARTNER_ONLY"
        assert SourceRegistryService.can_collect(src) is False
    finally:
        db.close()


@pytest.mark.parametrize(
    "mode,license_status,expected",
    [
        ("PUBLIC", "NOT_REQUIRED", True),
        ("CONDITIONAL", "LIMITED_USE", True),
        ("CONDITIONAL", "GOVERNMENT_PUBLIC", False),
        ("PARTNER_ONLY", "PARTNER_AGREEMENT", True),
        ("PARTNER_ONLY", "", False),
    ],
)
def test_access_policy_matrix(mode, license_status, expected):
    assert SourceRegistryService.can_collect(_approved_source(mode, license_status)) is expected
