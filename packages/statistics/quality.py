"""Data Quality & Plausibility Scoring Engine for Fare Observations."""

from typing import Any, Dict, Optional, Tuple


class QualityEngine:
    """Evaluates fare observations against plausibility and data integrity rules (PRD Section 19 & 62)."""

    MIN_PLAUSIBLE_PRICE: float = 1200.0  # Lowest typical Indian domestic fare
    MAX_PLAUSIBLE_PRICE: float = 60000.0  # Highest typical economy domestic spike

    @classmethod
    def evaluate(cls, observation: Dict[str, Any]) -> Tuple[float, str, Optional[str]]:
        """
        Evaluates a fare observation record.
        Returns: (quality_score: float, status: str, reason: Optional[str])

        Statuses:
        - ACCEPT (90 - 100)
        - ACCEPT_WITH_WARNING (70 - 89)
        - REVIEW (50 - 69)
        - REJECT (0 - 49)
        - MISSING_FOR_INDEX (80)
        - DEDUPLICATED (50)
        - SOURCE_ERROR (0)
        """
        # Rule 8: Source / Parser Error check
        if observation.get("source_error") or observation.get("parser_error"):
            return 0.0, "SOURCE_ERROR", "Source unavailable or parser crashed"

        # Rule 4: Missing route check
        origin = observation.get("origin")
        destination = observation.get("destination")
        if not origin or not destination or origin == destination:
            return 0.0, "REJECT", "Invalid or missing route coordinates"

        if not observation.get("carrier"):
            return 0.0, "REJECT", "Missing airline carrier"

        # Rule 2: Sold-out / Unavailable flight handling (PRD Section 17, 62)
        avail = str(observation.get("availability_status", "AVAILABLE")).upper()
        if avail in ("SOLD_OUT", "CANCELLED", "UNAVAILABLE"):
            return 80.0, "MISSING_FOR_INDEX", f"Flight is {avail} - excluded from price calculation"

        total_fare = observation.get("total_fare")
        base_fare = observation.get("base_fare")

        # Missing price check
        if total_fare is None or base_fare is None:
            return 0.0, "REJECT", "Fare amount is null or missing"

        try:
            total = float(total_fare)
            base = float(base_fare)
        except (ValueError, TypeError):
            return 0.0, "REJECT", "Invalid non-numeric fare values"

        # Rule 3: Negative or Zero Price (PRD Section 62)
        if total <= 0 or base <= 0:
            return 0.0, "REJECT", f"Non-positive fare amount observed: total={total}"

        # Rule 6: Duplicate check flag
        if observation.get("is_duplicate"):
            return (
                50.0,
                "DEDUPLICATED",
                "Duplicate observation key detected within identical search window",
            )

        # Rule 5: Decomposition Sum Check
        fuel = float(observation.get("fuel_surcharge", 0.0))
        taxes = float(observation.get("tax_amount", 0.0))
        udf = float(observation.get("development_fee", 0.0))
        convenience = float(observation.get("convenience_fee", 0.0))
        other = float(observation.get("other_fee", 0.0))

        component_sum = base + fuel + taxes + udf + convenience + other
        discrepancy = abs(total - component_sum)

        if discrepancy > 50.0:
            return (
                45.0,
                "REJECT",
                f"Severe fare decomposition mismatch: total={total} vs sum={component_sum}",
            )
        elif discrepancy > 5.0:
            return 75.0, "ACCEPT_WITH_WARNING", f"Minor component discrepancy of ₹{discrepancy:.2f}"

        # Rule 7: Extreme but valid price (PRD Section 21 & 62)
        if total < cls.MIN_PLAUSIBLE_PRICE or total > cls.MAX_PLAUSIBLE_PRICE:
            return (
                65.0,
                "REVIEW",
                f"Extreme price outlier: ₹{total} outside [₹{cls.MIN_PLAUSIBLE_PRICE}, ₹{cls.MAX_PLAUSIBLE_PRICE}] - retained for review",
            )

        # Rule 1: Valid Fare (PRD Section 62)
        return 98.0, "ACCEPT", None
