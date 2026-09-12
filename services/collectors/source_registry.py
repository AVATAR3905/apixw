"""Source Registry Service managing compliance states and collection authorization."""

import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import Source


class SourceComplianceError(Exception):
    """Raised when a source violates compliance or eligibility rules."""

    pass


class SourceRegistryService:
    """Manages the lifecycle, compliance review, and operational states of data sources."""

    # Valid Lifecycle States
    VALID_STATES = (
        "DISCOVERED",
        "REVIEW_REQUIRED",
        "APPROVED",
        "ACTIVE",
        "DEGRADED",
        "DISABLED",
        "DOWN",
    )

    # Allowed state machine transitions
    TRANSITIONS = {
        "DISCOVERED": ["REVIEW_REQUIRED", "DISABLED"],
        "REVIEW_REQUIRED": ["APPROVED", "DISABLED"],
        "APPROVED": ["ACTIVE", "DISABLED"],
        "ACTIVE": ["DEGRADED", "DOWN", "DISABLED"],
        "DEGRADED": ["ACTIVE", "DOWN", "DISABLED"],
        "DOWN": ["REVIEW_REQUIRED", "DISABLED"],
        "DISABLED": ["REVIEW_REQUIRED", "APPROVED"],
    }

    @classmethod
    def can_collect(cls, source: Source) -> bool:
        """
        Determines whether a source is legally and operationally eligible for live collection.
        Rule (PRD Section 12): Unapproved or disabled sources must never be collected.
        Access-policy rule: collection requires a license/permission that matches the
        source's declared `access_mode`:
          - PUBLIC: no additional license needed (robots may still apply).
          - CONDITIONAL: requires APPROVED permission plus a limited-use/research license.
          - PARTNER_ONLY: requires an explicit PARTNER_AGREEMENT (API/partner channel).
        """
        if not source.enabled:
            return False
        if source.permission_status != "APPROVED":
            return False
        if source.health_status in ("DOWN", "DISABLED"):
            return False

        access_mode = (source.access_mode or "PUBLIC").upper()
        license_status = (source.license_status or "").upper()
        if access_mode == "CONDITIONAL":
            return license_status in ("RESEARCH_EXEMPTION", "LIMITED_USE", "VERIFIED_PERMITTED")
        if access_mode == "PARTNER_ONLY":
            return license_status == "PARTNER_AGREEMENT"
        return True

    @classmethod
    def _blocked_reason(cls, source: Source) -> str:
        """Human-readable explanation of why a source cannot be collected."""
        if not source.enabled:
            return "source is disabled"
        if source.permission_status != "APPROVED":
            return f"permission_status is {source.permission_status!r}, not APPROVED"
        if source.health_status in ("DOWN", "DISABLED"):
            return f"health_status is {source.health_status!r}"
        access_mode = (source.access_mode or "PUBLIC").upper()
        license_status = (source.license_status or "").upper()
        if access_mode == "CONDITIONAL" and license_status not in (
            "RESEARCH_EXEMPTION",
            "LIMITED_USE",
            "VERIFIED_PERMITTED",
        ):
            return (
                "access_mode CONDITIONAL requires a limited-use/research license, "
                f"got {license_status!r}"
            )
        if access_mode == "PARTNER_ONLY" and license_status != "PARTNER_AGREEMENT":
            return f"access_mode PARTNER_ONLY requires PARTNER_AGREEMENT, got {license_status!r}"
        return ""

    @classmethod
    def transition_state(
        cls, db: Session, source_id: int, target_state: str, reviewer_notes: Optional[str] = None
    ) -> Source:
        """Validates and executes a state transition for a registered source."""
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise SourceComplianceError(f"Source with ID {source_id} not found")

        target_state = target_state.upper()
        if target_state not in cls.VALID_STATES:
            raise SourceComplianceError(f"Invalid target state: {target_state}")

        current_health = source.health_status
        allowed = cls.TRANSITIONS.get(current_health, [])

        if target_state not in allowed:
            raise SourceComplianceError(
                f"Illegal state transition from {current_health} to {target_state}. Allowed: {allowed}"
            )

        source.health_status = target_state
        if target_state == "ACTIVE":
            if source.permission_status != "APPROVED":
                raise SourceComplianceError(
                    "Cannot activate source: permission_status must be APPROVED before activation."
                )
            source.enabled = True
        elif target_state in ("DISABLED", "DOWN"):
            source.enabled = False

        source.last_reviewed_at = datetime.datetime.now(datetime.UTC)
        db.commit()
        db.refresh(source)
        return source

    @classmethod
    def approve_source(
        cls,
        db: Session,
        source_id: int,
        tos_status: str = "COMPLIANT",
        robots_status: str = "COMPLIANT",
        license_status: str = "VERIFIED_PERMITTED",
    ) -> Source:
        """Grants compliance approval after verifying legal and terms-of-service requirements."""
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise SourceComplianceError(f"Source with ID {source_id} not found")

        source.permission_status = "APPROVED"
        source.tos_status = tos_status
        source.robots_status = robots_status
        source.license_status = license_status
        source.health_status = "APPROVED"
        source.last_reviewed_at = datetime.datetime.now(datetime.UTC)

        db.commit()
        db.refresh(source)
        return source

    @classmethod
    def list_sources(cls, db: Session, active_only: bool = False) -> List[Source]:
        """Lists all registered sources."""
        query = db.query(Source)
        if active_only:
            query = query.filter(Source.enabled, Source.permission_status == "APPROVED")
        return query.all()
