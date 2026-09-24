"""DGCA Domestic Passenger Traffic Weighting & Basket Engine (PRD Section 22, 23, 35)."""

import csv
import datetime
import os
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import MethodologyVersion, Route, RouteWeight


class WeightCalculationError(Exception):
    """Raised when weight calculation violates statistical normalization rules."""

    pass


class DGCAWeightEngine:
    """Ingests DGCA city-pair domestic passenger statistics, computes bidirectional corridor weights, and manages version lineage."""

    METHODOLOGY_LIMITATION_NOTE = (
        "Route weights reflect boarded passenger volumes from official DGCA scheduled domestic reports, "
        "not route-level consumer price exposure. High-volume competitive trunk corridors (e.g. DEL-BOM) "
        "receive larger weights, while regional/thin corridors with high price vulnerability (e.g. DEL-IXS) "
        "receive smaller weights in the aggregate national index."
    )
    STANDARD_ROUTE_CODES = {
        "DEL-BOM",
        "DEL-BLR",
        "BOM-BLR",
        "DEL-CCU",
        "DEL-HYD",
        "BOM-MAA",
        "BLR-HYD",
        "DEL-MAA",
        "DEL-IXS",
        "DEL-DHM",
    }

    @classmethod
    def parse_traffic_csv(cls, csv_path: str) -> Dict[str, float]:
        """
        Parses DGCA city-pair traffic CSV and aggregates bidirectional passenger traffic.
        Example: Combines DEL -> BOM (1.65M) + BOM -> DEL (1.60M) into DEL-BOM (3.25M).
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"DGCA traffic CSV not found at {csv_path}")

        directional_flows: Dict[str, float] = {}

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                origin = row["origin_airport"].strip().upper()
                dest = row["destination_airport"].strip().upper()
                vol = float(row["passenger_volume"])

                corridor_pair = f"{origin}-{dest}"
                directional_flows[corridor_pair] = directional_flows.get(corridor_pair, 0.0) + vol

        # Aggregate bidirectional corridors (combining A-B and B-A)
        bidirectional_corridors: Dict[str, float] = {}
        processed_pairs = set()

        for pair, vol in directional_flows.items():
            if pair in processed_pairs:
                continue

            origin, dest = pair.split("-")
            reverse_pair = f"{dest}-{origin}"
            total_vol = vol + directional_flows.get(reverse_pair, 0.0)

            # Match standard route codes
            if pair in cls.STANDARD_ROUTE_CODES:
                canonical_pair = pair
            elif reverse_pair in cls.STANDARD_ROUTE_CODES:
                canonical_pair = reverse_pair
            else:
                canonical_pair = "-".join(sorted([origin, dest]))

            bidirectional_corridors[canonical_pair] = total_vol
            processed_pairs.add(pair)
            processed_pairs.add(reverse_pair)

        return bidirectional_corridors

    @classmethod
    def compute_normalized_weights(cls, volumes: Dict[str, float]) -> Dict[str, float]:
        """
        Calculates normalized Laspeyres route weights:
        w_j = V_j / sum(V_k)

        Strict constraint: sum(w_j) == 1.000000 within 1e-6 tolerance.
        """
        if not volumes:
            raise WeightCalculationError("Volumes dictionary cannot be empty")

        negative = {route: vol for route, vol in volumes.items() if vol < 0}
        if negative:
            raise WeightCalculationError(
                f"Passenger volume cannot be negative: {negative}. A single bad "
                "figure (e.g. a DGCA source-data entry error) must not be allowed "
                "to silently flip that route's weight sign in the national index."
            )

        total_volume = sum(volumes.values())
        if total_volume <= 0:
            raise WeightCalculationError(
                f"Total volume must be strictly positive, got {total_volume}"
            )

        weights = {route: vol / total_volume for route, vol in volumes.items()}

        # Strict validation
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 1e-6:
            raise WeightCalculationError(
                f"Weights normalization failed! Sum of weights is {weight_sum:.8f}, must equal 1.0 ± 1e-6."
            )

        return {route: round(w, 6) for route, w in weights.items()}

    @classmethod
    def persist_weights_version(
        cls,
        db: Session,
        csv_path: str,
        version_tag: str = "DGCA_2026_V1",
        effective_from: Optional[datetime.date] = None,
        period: str = "2025-Q4",
    ) -> List[RouteWeight]:
        """
        Parses traffic, computes normalized weights, retires older weights, and persists new version.
        """
        if effective_from is None:
            effective_from = datetime.date(2026, 1, 1)

        corridor_volumes = cls.parse_traffic_csv(csv_path)
        normalized_weights = cls.compute_normalized_weights(corridor_volumes)

        created_weights: List[RouteWeight] = []

        routes = db.query(Route).all()
        route_map = {r.route_code: r for r in routes}

        # Expire older active weights if present
        yesterday = effective_from - datetime.timedelta(days=1)
        prior_weights = (
            db.query(RouteWeight)
            .filter(
                RouteWeight.effective_to.is_(None),
                RouteWeight.effective_from < effective_from,
            )
            .all()
        )
        for pw in prior_weights:
            pw.effective_to = yesterday

        for route_code, weight in normalized_weights.items():
            route = route_map.get(route_code)
            if not route:
                continue

            vol = corridor_volumes.get(route_code, 0.0)

            # Upsert: skip creating a duplicate row if this exact version already exists
            existing = (
                db.query(RouteWeight)
                .filter(
                    RouteWeight.route_id == route.id,
                    RouteWeight.methodology_version == version_tag,
                    RouteWeight.effective_from == effective_from,
                )
                .first()
            )
            if existing:
                existing.passenger_volume = vol
                existing.weight = weight
                existing.effective_to = None
                created_weights.append(existing)
                continue

            rw = RouteWeight(
                route_id=route.id,
                passenger_volume=vol,
                weight=weight,
                source=f"DGCA Domestic Scheduled Passenger Traffic Report {period}",
                period=period,
                methodology_version=version_tag,
                effective_from=effective_from,
                effective_to=None,
            )
            db.add(rw)
            created_weights.append(rw)

        # Update methodology version notes with weighting limitation
        methodology = (
            db.query(MethodologyVersion).filter(MethodologyVersion.version == "APIX-2.0").first()
        )
        if methodology:
            methodology.notes = (
                f"{methodology.notes}\n\n[Weighting Disclosure]: {cls.METHODOLOGY_LIMITATION_NOTE}"
            )

        db.commit()
        return created_weights

    @classmethod
    def get_active_weights(
        cls, db: Session, target_date: Optional[datetime.date] = None
    ) -> Dict[str, float]:
        """Returns the active normalized route weights effective on a given observation date."""
        if target_date is None:
            target_date = datetime.date.today()

        weights_db = (
            db.query(RouteWeight, Route)
            .join(Route, RouteWeight.route_id == Route.id)
            .filter(
                RouteWeight.effective_from <= target_date,
                (RouteWeight.effective_to.is_(None)) | (RouteWeight.effective_to >= target_date),
            )
            .all()
        )

        return {route.route_code: rw.weight for rw, route in weights_db}
