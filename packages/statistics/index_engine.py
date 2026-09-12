"""Modified Laspeyres Airfare Price Index Engine with Unpooled Lead-Time Architecture."""

from typing import Any, Dict


class IndexCalculationError(Exception):
    """Raised when index calculation encounters invalid mathematical inputs."""

    pass


class AirfareIndexEngine:
    """Computes Modified Laspeyres Price Indices with authentic DGCA passenger weights."""

    HEADLINE_ANCHOR_HORIZON: int = 15  # Standard T+15 headline anchor
    MINIMUM_ACCEPTABLE_COVERAGE: float = 80.0  # Percentage

    @classmethod
    def calculate_route_relative(cls, current_price: float, base_price: float) -> float:
        """Calculates price relative R_{j,t} = P_{j,t} / P_{j,0}."""
        if base_price <= 0:
            raise IndexCalculationError(
                f"Base period price must be strictly positive, got {base_price}"
            )
        if current_price <= 0:
            raise IndexCalculationError(
                f"Current price must be strictly positive, got {current_price}"
            )
        return current_price / base_price

    @classmethod
    def calculate_national_index(
        cls,
        route_prices: Dict[str, float],
        base_prices: Dict[str, float],
        route_weights: Dict[str, float],
        allow_missing: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculates Modified Laspeyres Index:
        I_t = 100 * sum(w_j * (P_{j,t} / P_{j,0}))

        Where:
        - route_prices: {route_code: current_representative_price}
        - base_prices: {route_code: base_period_representative_price}
        - route_weights: {route_code: normalized_weight} (sum = 1.0)
        """
        total_basket_count = len(route_weights)
        if total_basket_count == 0:
            raise IndexCalculationError("Route weights dictionary cannot be empty")

        # Validate weights sum to 1.0
        weight_sum = sum(route_weights.values())
        if not (0.999 <= weight_sum <= 1.001):
            raise IndexCalculationError(f"Route weights must sum to 1.0, got {weight_sum:.6f}")

        valid_routes = []
        route_relatives: Dict[str, float] = {}
        route_indices: Dict[str, float] = {}
        route_contributions: Dict[str, float] = {}
        weighted_relatives = []
        active_weights = []

        for route_code, weight in route_weights.items():
            curr_p = route_prices.get(route_code)
            base_p = base_prices.get(route_code)

            # Check if valid price exists for route
            if curr_p is not None and curr_p > 0 and base_p is not None and base_p > 0:
                rel = curr_p / base_p
                route_relatives[route_code] = round(rel, 4)
                route_indices[route_code] = round(rel * 100.0, 2)
                weighted_rel = weight * rel
                route_contributions[route_code] = round(weighted_rel * 100.0, 2)

                weighted_relatives.append(weighted_rel)
                active_weights.append(weight)
                valid_routes.append(route_code)

        valid_count = len(valid_routes)
        coverage_rate = (valid_count / total_basket_count) * 100.0
        is_low_coverage = coverage_rate < cls.MINIMUM_ACCEPTABLE_COVERAGE

        if valid_count == 0:
            raise IndexCalculationError(
                "Zero valid route observations available to calculate index"
            )

        # If some routes are missing, re-normalize weights over active routes to avoid artificial deflation
        if valid_count < total_basket_count:
            active_weight_sum = sum(active_weights)
            if active_weight_sum > 0:
                index_value = 100.0 * (sum(weighted_relatives) / active_weight_sum)
            else:
                index_value = 100.0
        else:
            index_value = 100.0 * sum(weighted_relatives)

        return {
            "index_value": round(float(index_value), 2),
            "coverage_rate": round(float(coverage_rate), 1),
            "is_low_coverage": is_low_coverage,
            "total_basket_routes": total_basket_count,
            "valid_routes_count": valid_count,
            "route_indices": route_indices,
            "route_relatives": route_relatives,
            "route_contributions": route_contributions,
        }

    @classmethod
    def calculate_lead_time_elasticity(
        cls,
        route_lead_time_prices: Dict[int, float],
    ) -> Dict[str, Any]:
        """
        Calculates lead-time price progression and dynamic surge multiplier (T+1 / T+45).
        Inputs: {1: 9500.0, 7: 6100.0, 14: 4800.0, 30: 4200.0, 45: 3900.0}
        """
        t1 = route_lead_time_prices.get(1)
        t45 = route_lead_time_prices.get(45)

        multiplier = None
        if t1 is not None and t45 is not None and t45 > 0:
            multiplier = round(float(t1 / t45), 2)

        sorted_curve = [
            {"advance_days": h, "price": route_lead_time_prices[h]}
            for h in sorted(route_lead_time_prices.keys(), reverse=True)
            if route_lead_time_prices.get(h) is not None
        ]

        return {
            "lead_time_curve": sorted_curve,
            "surge_multiplier_t1_t45": multiplier,
            "t1_price": t1,
            "t15_price": route_lead_time_prices.get(15),
            "t14_price": route_lead_time_prices.get(15, route_lead_time_prices.get(14)),
            "t45_price": t45,
        }
