"""Fare Observation Normalization & Decomposition Engine."""

from typing import Any, Dict


class NormalizationError(Exception):
    """Raised when fare normalization fails validation."""

    pass


class FareNormalizer:
    """Normalizes raw parsed fare records into validated observation models."""

    DECOMPOSITION_TOLERANCE: float = 5.0  # INR tolerance for component sum

    @classmethod
    def normalize_observation(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes and validates a single fare observation record."""
        # Validate required identifiers
        origin = str(raw.get("origin", "")).strip().upper()
        destination = str(raw.get("destination", "")).strip().upper()
        if not origin or not destination or origin == destination:
            raise NormalizationError(f"Invalid route: {origin} -> {destination}")

        carrier = str(raw.get("carrier", "")).strip().upper()
        if not carrier:
            raise NormalizationError("Missing carrier code")

        flight_number = str(raw.get("flight_number", "")).strip().upper()
        if not flight_number:
            raise NormalizationError("Missing flight number")

        # Availability status
        avail = str(raw.get("availability_status", "AVAILABLE")).strip().upper()
        if avail not in ("AVAILABLE", "SOLD_OUT", "CANCELLED", "UNAVAILABLE"):
            avail = "AVAILABLE"

        # Advance purchase horizon
        advance_days = int(raw.get("advance_purchase_days", 14))
        if advance_days not in (1, 7, 14, 15, 30, 45):
            # Normalise to standard buckets if near
            if advance_days <= 2:
                advance_days = 1
            elif advance_days <= 10:
                advance_days = 7
            elif advance_days <= 20:
                advance_days = 14
            elif advance_days <= 37:
                advance_days = 30
            else:
                advance_days = 45

        # Cabin & fare family
        cabin = str(raw.get("cabin_class", "ECONOMY")).strip().upper()
        fare_family = str(raw.get("fare_family", "BASIC")).strip().upper()

        # Handle Sold-out and Cancelled cases explicitly
        if avail in ("SOLD_OUT", "CANCELLED", "UNAVAILABLE"):
            return {
                "origin": origin,
                "destination": destination,
                "route_code": f"{origin}-{destination}",
                "carrier": carrier,
                "flight_number": flight_number,
                "cabin_class": cabin,
                "fare_family": fare_family,
                "advance_purchase_days": advance_days,
                "availability_status": avail,
                "is_carrier_min_fare": False,
                "base_fare": None,
                "fuel_surcharge": 0.0,
                "tax_amount": 0.0,
                "development_fee": 0.0,
                "convenience_fee": 0.0,
                "other_fee": 0.0,
                "total_fare": None,
                "currency": "INR",
                "is_synthetic": bool(raw.get("is_synthetic", False)),
            }

        # Numeric price components
        try:
            total_fare = float(raw.get("total_fare", 0.0))
            base_fare = float(raw.get("base_fare", total_fare * 0.75))
            fuel_surcharge = float(raw.get("fuel_surcharge", 0.0))
            tax_amount = float(raw.get("tax_amount", total_fare * 0.05))  # ~5% GST
            development_fee = float(raw.get("development_fee", 0.0))  # UDF
            convenience_fee = float(raw.get("convenience_fee", 0.0))
            other_fee = float(raw.get("other_fee", 0.0))
        except (ValueError, TypeError) as e:
            raise NormalizationError(f"Invalid numeric fare values: {e}")

        # Check negative prices
        if total_fare < 0 or base_fare < 0:
            raise NormalizationError(
                f"Negative price observed: total={total_fare}, base={base_fare}"
            )

        # Component sum validation
        component_sum = (
            base_fare + fuel_surcharge + tax_amount + development_fee + convenience_fee + other_fee
        )
        discrepancy = abs(total_fare - component_sum)

        if discrepancy > cls.DECOMPOSITION_TOLERANCE:
            # Rebalance discrepancy into other_fee if small, else retain for quality engine warning
            if discrepancy <= 50.0:
                other_fee += total_fare - component_sum

        return {
            "origin": origin,
            "destination": destination,
            "route_code": f"{origin}-{destination}",
            "carrier": carrier,
            "flight_number": flight_number,
            "cabin_class": cabin,
            "fare_family": fare_family,
            "advance_purchase_days": advance_days,
            "availability_status": avail,
            "is_carrier_min_fare": bool(raw.get("is_carrier_min_fare", False)),
            "base_fare": round(base_fare, 2),
            "fuel_surcharge": round(fuel_surcharge, 2),
            "tax_amount": round(tax_amount, 2),
            "development_fee": round(development_fee, 2),
            "convenience_fee": round(convenience_fee, 2),
            "other_fee": round(other_fee, 2),
            "total_fare": round(total_fare, 2),
            "currency": "INR",
            "is_synthetic": bool(raw.get("is_synthetic", False)),
        }
