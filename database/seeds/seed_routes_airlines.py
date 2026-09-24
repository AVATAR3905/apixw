"""Seed script for 10 balanced route corridors, scheduled airlines, and initial data sources.

Route weights are intentionally NOT created here. DGCAWeights are owned by
`packages.statistics.weights.DGCAWeightEngine.persist_weights_version` so that
weight versioning and lineage remain consistent (exactly one active set at a time).
"""
import datetime

from sqlalchemy.orm import Session

from database.session import SessionLocal
from packages.schemas.models import Airline, MethodologyVersion, Route, Source
from packages.shared.time_utils import utcnow


def seed_routes(db: Session):
    """Seed 10 balanced routes (8 Metro Trunk + 2 Regional Thin)."""
    corridors = [
        # Metro Trunk Corridors
        {
            "origin": "Delhi",
            "destination": "Mumbai",
            "origin_airport": "DEL",
            "destination_airport": "BOM",
            "route_code": "DEL-BOM",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.184,
            "volume": 3250000,
        },
        {
            "origin": "Delhi",
            "destination": "Bengaluru",
            "origin_airport": "DEL",
            "destination_airport": "BLR",
            "route_code": "DEL-BLR",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.142,
            "volume": 2510000,
        },
        {
            "origin": "Mumbai",
            "destination": "Bengaluru",
            "origin_airport": "BOM",
            "destination_airport": "BLR",
            "route_code": "BOM-BLR",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.121,
            "volume": 2140000,
        },
        {
            "origin": "Delhi",
            "destination": "Kolkata",
            "origin_airport": "DEL",
            "destination_airport": "CCU",
            "route_code": "DEL-CCU",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.105,
            "volume": 1850000,
        },
        {
            "origin": "Delhi",
            "destination": "Hyderabad",
            "origin_airport": "DEL",
            "destination_airport": "HYD",
            "route_code": "DEL-HYD",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.098,
            "volume": 1730000,
        },
        {
            "origin": "Mumbai",
            "destination": "Chennai",
            "origin_airport": "BOM",
            "destination_airport": "MAA",
            "route_code": "BOM-MAA",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.086,
            "volume": 1520000,
        },
        {
            "origin": "Bengaluru",
            "destination": "Hyderabad",
            "origin_airport": "BLR",
            "destination_airport": "HYD",
            "route_code": "BLR-HYD",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.079,
            "volume": 1390000,
        },
        {
            "origin": "Delhi",
            "destination": "Chennai",
            "origin_airport": "DEL",
            "destination_airport": "MAA",
            "route_code": "DEL-MAA",
            "corridor_type": "METRO_TRUNK",
            "weight": 0.075,
            "volume": 1320000,
        },
        # Regional / Thin Corridors (Price Vulnerability & Airfare Inequality)
        {
            "origin": "Delhi",
            "destination": "Silchar",
            "origin_airport": "DEL",
            "destination_airport": "IXS",
            "route_code": "DEL-IXS",
            "corridor_type": "REGIONAL_THIN",
            "weight": 0.058,
            "volume": 1020000,
        },
        {
            "origin": "Delhi",
            "destination": "Dharamshala",
            "origin_airport": "DEL",
            "destination_airport": "DHM",
            "route_code": "DEL-DHM",
            "corridor_type": "REGIONAL_THIN",
            "weight": 0.052,
            "volume": 920000,
        },
    ]

    for c in corridors:
        existing = db.query(Route).filter(Route.route_code == c["route_code"]).first()
        if not existing:
            route = Route(
                origin=c["origin"],
                destination=c["destination"],
                origin_airport=c["origin_airport"],
                destination_airport=c["destination_airport"],
                route_code=c["route_code"],
                corridor_type=c["corridor_type"],
                active=True,
            )
            db.add(route)


def seed_airlines(db: Session):
    """Seed top scheduled Indian domestic carriers."""
    carriers = [
        {"code": "6E", "name": "IndiGo", "is_scheduled": True},
        {"code": "AI", "name": "Air India", "is_scheduled": True},
        {"code": "SG", "name": "SpiceJet", "is_scheduled": True},
        {"code": "QP", "name": "Akasa Air", "is_scheduled": True},
        {"code": "IX", "name": "AI Express", "is_scheduled": True},
    ]

    for carrier in carriers:
        existing = db.query(Airline).filter(Airline.code == carrier["code"]).first()
        if not existing:
            db.add(
                Airline(
                    code=carrier["code"],
                    name=carrier["name"],
                    is_scheduled=carrier["is_scheduled"],
                    active=True,
                )
            )


def seed_sources(db: Session):
    """Seed compliant data sources and pipeline registries."""
    sources = [
        {
            "name": "Synthetic Pipeline Verification Feed",
            "type": "SYNTHETIC_FEED",
            "access_method": "DETERMINISTIC_MODEL",
            "access_mode": "PUBLIC",
            "permission_status": "DEPRECATED_DEVELOPMENT",
            "tos_status": "COMPLIANT",
            "robots_status": "NOT_APPLICABLE",
            "license_status": "INTERNAL_VERIFICATION",
            "rate_limit": 1000,
            "enabled": False,
            "health_status": "HEALTHY",
        },
        {
            "name": "DGCA Official Passenger Statistics",
            "type": "GOVERNMENT_DATA",
            "access_method": "PUBLIC_DATASET",
            "access_mode": "PUBLIC",
            "permission_status": "APPROVED",
            "tos_status": "OPEN_GOVERNMENT_DATA",
            "robots_status": "COMPLIANT",
            "license_status": "GOVERNMENT_PUBLIC",
            "rate_limit": 60,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "name": "MoSPI CPI Benchmark Feed",
            "type": "GOVERNMENT_DATA",
            "access_method": "PUBLIC_DATASET",
            "access_mode": "PUBLIC",
            "permission_status": "APPROVED",
            "tos_status": "OPEN_GOVERNMENT_DATA",
            "robots_status": "COMPLIANT",
            "license_status": "GOVERNMENT_PUBLIC",
            "rate_limit": 60,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "name": "Public Flight Search Gateway",
            "type": "OTA",
            "access_method": "PLAYWRIGHT",
            "access_mode": "CONDITIONAL",
            "permission_status": "REVIEW_REQUIRED",
            "tos_status": "PENDING_REVIEW",
            "robots_status": "CHECKING",
            "license_status": "RESEARCH_EXEMPTION",
            "rate_limit": 10,
            "enabled": False,
            "health_status": "HEALTHY",
        },
        {
            "name": "Carrier Direct Booking Scraper",
            "type": "CARRIER_DIRECT",
            "access_method": "PLAYWRIGHT_DIRECT",
            "access_mode": "PUBLIC",
            "permission_status": "APPROVED",
            "tos_status": "PUBLIC_SEARCH_PORTAL",
            "robots_status": "COMPLIANT",
            "license_status": "PRIMARY_AUTHORITATIVE",
            "rate_limit": 20,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "name": "Google Flights RPC Validator & Fallback",
            "type": "AGGREGATOR_RPC",
            "access_method": "RPC_FAST_FLIGHTS",
            "access_mode": "PARTNER_ONLY",
            "permission_status": "APPROVED",
            "tos_status": "SEARCH_ENGINE_RPC",
            "robots_status": "COMPLIANT",
            "license_status": "VALIDATOR_FALLBACK",
            "rate_limit": 30,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        # Top 6 Indian OTAs (source ids 7-12 align with the OTA scraper registry
        # in services/collectors/ota/ and the /api/v1/ota/sources-status endpoint).
        {
            "id": 7,
            "name": "MakeMyTrip India",
            "type": "OTA",
            "access_method": "PLAYWRIGHT",
            "access_mode": "CONDITIONAL",
            "permission_status": "APPROVED",
            "tos_status": "PUBLIC_FLIGHT_SEARCH",
            "robots_status": "COMPLIANT",
            "license_status": "AGGREGATOR_RESEARCH",
            "rate_limit": 15,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "id": 8,
            "name": "Ixigo Flights",
            "type": "OTA",
            "access_method": "PLAYWRIGHT",
            "access_mode": "CONDITIONAL",
            "permission_status": "APPROVED",
            "tos_status": "PUBLIC_FLIGHT_SEARCH",
            "robots_status": "COMPLIANT",
            "license_status": "AGGREGATOR_RESEARCH",
            "rate_limit": 15,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "id": 9,
            "name": "EaseMyTrip",
            "type": "OTA",
            "access_method": "PLAYWRIGHT",
            "access_mode": "CONDITIONAL",
            "permission_status": "APPROVED",
            "tos_status": "PUBLIC_FLIGHT_SEARCH",
            "robots_status": "COMPLIANT",
            "license_status": "AGGREGATOR_RESEARCH",
            "rate_limit": 15,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "id": 10,
            "name": "Yatra Online",
            "type": "OTA",
            "access_method": "PLAYWRIGHT",
            "access_mode": "CONDITIONAL",
            "permission_status": "APPROVED",
            "tos_status": "PUBLIC_FLIGHT_SEARCH",
            "robots_status": "COMPLIANT",
            "license_status": "AGGREGATOR_RESEARCH",
            "rate_limit": 15,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "id": 11,
            "name": "Cleartrip",
            "type": "OTA",
            "access_method": "PLAYWRIGHT",
            "access_mode": "CONDITIONAL",
            "permission_status": "APPROVED",
            "tos_status": "PUBLIC_FLIGHT_SEARCH",
            "robots_status": "COMPLIANT",
            "license_status": "AGGREGATOR_RESEARCH",
            "rate_limit": 15,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        {
            "id": 12,
            "name": "Skyscanner India",
            "type": "METASEARCH",
            "access_method": "PLAYWRIGHT",
            "access_mode": "CONDITIONAL",
            "permission_status": "APPROVED",
            "tos_status": "PUBLIC_FLIGHT_SEARCH",
            "robots_status": "COMPLIANT",
            "license_status": "AGGREGATOR_RESEARCH",
            "rate_limit": 15,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        # Licensed GDS / partner-API tier (source id 13) -- NOT scraped. These
        # feeds carry PARTNER_ONLY access policy and require a PARTNER_AGREEMENT
        # license, matching SourceRegistryService.can_collect. Air India and
        # IndiGo are both Amadeus-distributed, so this one key covers the two
        # carriers whose portals reject programmatic access at the transport
        # level. Credentials are optional to *run*: without a key the adapter
        # degrades to the tagged calibrated fallback.
        {
            "id": 13,
            "name": "Amadeus Self-Service API",
            "type": "GDS_API",
            "access_method": "REST_API",
            "access_mode": "PARTNER_ONLY",
            "permission_status": "APPROVED",
            "tos_status": "PARTNER_API_AGREEMENT",
            "robots_status": "NOT_APPLICABLE",
            "license_status": "PARTNER_AGREEMENT",
            "rate_limit": 30,
            "enabled": True,
            "health_status": "HEALTHY",
        },
        # Sabre Developer Hub (source id 14) -- same licensed GDS tier. Free,
        # self-service registration (create app -> User ID/Password -> OAuth
        # token), Flight Shop API on the PLAY cert environment. This became the
        # main self-service licensed route after Amadeus decommissioned its free
        # portal on 2026-07-17.
        {
            "id": 14,
            "name": "Sabre Developer Hub",
            "type": "GDS_API",
            "access_method": "REST_API",
            "access_mode": "PARTNER_ONLY",
            "permission_status": "APPROVED",
            "tos_status": "PARTNER_API_AGREEMENT",
            "robots_status": "NOT_APPLICABLE",
            "license_status": "PARTNER_AGREEMENT",
            "rate_limit": 30,
            "enabled": True,
            "health_status": "HEALTHY",
        },
    ]

    for s in sources:
        existing = db.query(Source).filter(Source.name == s["name"]).first()
        if not existing:
            db.add(
                Source(
                    id=s.get("id"),
                    name=s["name"],
                    type=s["type"],
                    access_method=s["access_method"],
                    access_mode=s.get("access_mode", "PUBLIC"),
                    permission_status=s["permission_status"],
                    tos_status=s["tos_status"],
                    robots_status=s["robots_status"],
                    license_status=s["license_status"],
                    rate_limit=s["rate_limit"],
                    enabled=s["enabled"],
                    health_status=s["health_status"],
                    last_reviewed_at=utcnow(),
                )
            )
        else:
            # Sync governance/policy fields so reseeding converges the registry.
            existing.access_mode = s.get("access_mode", "PUBLIC")
            existing.license_status = s["license_status"]
            existing.permission_status = s["permission_status"]
            existing.enabled = s["enabled"]


def seed_methodology(db: Session):
    """Seed APIX-2.0 transparent methodology definition."""
    version = "APIX-2.0"
    existing = db.query(MethodologyVersion).filter(MethodologyVersion.version == version).first()
    if not existing:
        db.add(
            MethodologyVersion(
                version=version,
                name="India Airfare Price Index (Modified Laspeyres with Fare-Mix Protection & T+15 Anchor)",
                base_period="2026-08-01",
                anchor_lead_time="T+15",
                price_estimator="LOWEST_ECONOMY_JEVONS_GEOMETRIC_MEAN",
                missing_data_method="EXCLUDE_SOLD_OUT_RECORD_COVERAGE",
                outlier_method="ROBUST_MEDIAN_FILTER",
                weight_method="DGCA_BIDIRECTIONAL_PASSENGER_VOLUME",
                formula=(
                    "I_t = 100 * sum(w_j * (P_{j,t,T+15} / P_{j,0,T+15})); "
                    "P_{j,t,h} = exp(mean(ln P_{j,t,h,c}))"
                ),
                effective_from=datetime.date(2026, 1, 1),
                notes=(
                    "APIX-2.0 eliminates fare-mix distortion by taking the minimum "
                    "available non-refundable economy fare per scheduled carrier before "
                    "cross-carrier Jevons geometric-mean estimation (IMF CPI Manual 2020 "
                    "Ch.10). "
                    "The headline national index is anchored at T+15, while T+1, T+7, "
                    "T+15, T+30, T+45 are computed as unpooled sub-indices. Both Base "
                    "Fare and Total Price series are supported. "
                    "Route weights reflect DGCA boarded passenger volumes across 8 metro "
                    "trunks and 2 regional corridors."
                ),
            )
        )


def seed_reference_data():
    """Seed all reference data (routes, airlines, sources, methodology) in one commit.

    DGCA route weights are created by `DGCAWeightEngine.persist_weights_version`
    (invoked by `services.seed_demo_data`) so that weight lineage stays consistent.
    """
    db = SessionLocal()
    try:
        seed_routes(db)
        seed_airlines(db)
        seed_sources(db)
        seed_methodology(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_seed():
    """Run all database seeders (routes, airlines, sources, methodology)."""
    db = SessionLocal()
    try:
        seed_routes(db)
        seed_airlines(db)
        seed_sources(db)
        seed_methodology(db)
        db.commit()
        print("Database seeding completed successfully:")
        print(f" - Routes: {db.query(Route).count()}")
        print(f" - Airlines: {db.query(Airline).count()}")
        print(f" - Sources: {db.query(Source).count()}")
        print(f" - Methodology: {db.query(MethodologyVersion).count()}")
        print(" - Weights: run `python -m services.seed_demo_data` to persist DGCA route weights.")
    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
