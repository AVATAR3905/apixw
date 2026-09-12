"""Cross-OTA Canonical Pricing & Fair-Fare Resolution Engine.

Implements statistical resolution across disparate OTA quotes:
1. Harmonized Platform Median (Official MoSPI CPI Recommendation)
2. Minimum Walkaway Fare (Rational Consumer Shopping Benchmark)
3. Inter-Platform Price Dispersion & Spread %
4. Platform Convenience Fee & Markup Ranking
"""

import statistics
from typing import Any, Dict, List


class CanonicalPricer:
    """Computes authoritative index prices and dispersion metrics from multi-source flight clusters."""

    @classmethod
    def price_common_flight(cls, cluster: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes a clustered flight entity with quotes from multiple sources,
        and computes canonical pricing and parity dispersion.
        """
        quotes = cluster.get("all_quotes", [])
        if not quotes:
            return {}

        total_fares = [float(q["total_fare"]) for q in quotes if q.get("total_fare")]
        if not total_fares:
            return {}

        median_fare = round(statistics.median(total_fares), 2)
        min_fare = round(min(total_fares), 2)
        max_fare = round(max(total_fares), 2)
        spread_inr = round(max_fare - min_fare, 2)
        spread_pct = round((spread_inr / median_fare) * 100, 2) if median_fare > 0 else 0.0

        # Find cheapest source
        cheapest_quote = min(quotes, key=lambda q: float(q.get("total_fare", 999999)))
        cheapest_source = cheapest_quote.get("source_name", "Unknown")

        # Find carrier direct quote if present
        direct_quote = None
        for q in quotes:
            if "Carrier Direct" in q.get("source_name", "") or q.get("source_id") == 5:
                direct_quote = q
                break
        direct_fare = float(direct_quote["total_fare"]) if direct_quote else None

        # Build clean platform matrix
        platform_matrix: Dict[str, Dict[str, Any]] = {}
        for q in quotes:
            s_name = q.get("source_name", "Unknown")
            tot = float(q.get("total_fare", 0))
            markup_vs_direct = round(tot - direct_fare, 2) if direct_fare is not None else 0.0

            platform_matrix[s_name] = {
                "source_name": s_name,
                "source_domain": q.get("source_domain", ""),
                "base_fare": float(q.get("base_fare", 0)),
                "taxes_and_fees": float(q.get("fuel_surcharge", 0))
                + float(q.get("udf_adf", 0))
                + float(q.get("gst_taxes", 0)),
                "convenience_fee": float(q.get("convenience_fee", 0)),
                "promotional_discount": float(q.get("promotional_discount", 0)),
                "total_fare": tot,
                "is_cheapest": (tot == min_fare),
                "markup_vs_direct": markup_vs_direct,
            }

        return {
            "flight_number": cluster["flight_number"],
            "carrier_code": cluster["carrier_code"],
            "carrier_name": cluster["carrier_name"],
            "origin_airport": cluster["origin_airport"],
            "destination_airport": cluster["destination_airport"],
            "travel_date": cluster["travel_date"],
            "departure_time": cluster["departure_time"],
            "arrival_time": cluster["arrival_time"],
            "canonical_median_fare": median_fare,
            "min_walkaway_fare": min_fare,
            "max_observed_fare": max_fare,
            "carrier_direct_fare": direct_fare,
            "spread_inr": spread_inr,
            "spread_pct": spread_pct,
            "cheapest_source": cheapest_source,
            "sources_count": len(platform_matrix),
            "platform_matrix": platform_matrix,
        }

    @classmethod
    def compute_dispersion_ranking(
        cls,
        priced_flights: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Computes network-wide dispersion statistics:
        - Ranking of platforms by convenience fee
        - Ranking by cheapest flight win-rate
        - Average markup over direct airline price
        """
        platform_stats: Dict[str, Dict[str, Any]] = {}
        total_flights = len(priced_flights)

        for pf in priced_flights:
            matrix = pf.get("platform_matrix", {})
            for s_name, pdata in matrix.items():
                if s_name not in platform_stats:
                    platform_stats[s_name] = {
                        "source_name": s_name,
                        "domain": pdata.get("source_domain", ""),
                        "quotes_count": 0,
                        "cheapest_count": 0,
                        "total_convenience_fee": 0.0,
                        "total_markup_vs_direct": 0.0,
                    }

                platform_stats[s_name]["quotes_count"] += 1
                if pdata.get("is_cheapest"):
                    platform_stats[s_name]["cheapest_count"] += 1
                platform_stats[s_name]["total_convenience_fee"] += pdata.get("convenience_fee", 0.0)
                platform_stats[s_name]["total_markup_vs_direct"] += pdata.get(
                    "markup_vs_direct", 0.0
                )

        rankings = []
        for s_name, s in platform_stats.items():
            qc = s["quotes_count"] or 1
            avg_fee = round(s["total_convenience_fee"] / qc, 2)
            avg_markup = round(s["total_markup_vs_direct"] / qc, 2)
            win_rate = (
                round((s["cheapest_count"] / total_flights) * 100, 1) if total_flights > 0 else 0.0
            )

            rankings.append(
                {
                    "source_name": s_name,
                    "domain": s["domain"],
                    "quotes_count": s["quotes_count"],
                    "cheapest_win_rate_pct": win_rate,
                    "average_convenience_fee": avg_fee,
                    "average_markup_over_direct": avg_markup,
                }
            )

        # Sort by cheapest win-rate descending
        rankings.sort(key=lambda r: r["cheapest_win_rate_pct"], reverse=True)

        return {
            "total_flights_analyzed": total_flights,
            "platform_rankings": rankings,
        }
