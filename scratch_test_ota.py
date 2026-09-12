from packages.statistics.canonical_pricer import CanonicalPricer
from packages.statistics.flight_matcher import FlightEntityMatcher
from services.collectors.ota.multi_source_orchestrator import MultiSourceFlightOrchestrator

orchestrator = MultiSourceFlightOrchestrator()
res = orchestrator.collect_corridor_all_sources(route_code="DEL-BOM", advance_days=14)
print("Total quotes collected:", res["total_quotes_collected"])
print("Carrier quotes count:", res["carrier_quotes_count"])
print("OTA sources active:", list(res["ota_quotes_by_source"].keys()))

clusters = FlightEntityMatcher.cluster_common_flights(res["all_quotes"])
print("Common flight clusters count:", len(clusters))

priced = [CanonicalPricer.price_common_flight(c) for c in clusters.values()]
first = priced[0]
print("Sample flight:", first["flight_number"], first["carrier_name"])
print("Canonical Median Fare:", first["canonical_median_fare"])
print("Min Walkaway Fare:", first["min_walkaway_fare"], "Cheapest on:", first["cheapest_source"])
print("Spread INR:", first["spread_inr"], "Spread Pct:", first["spread_pct"])
for k, v in first["platform_matrix"].items():
    print(
        f"  Platform {k}: Total=INR {v['total_fare']}, Base=INR {v['base_fare']}, Fee=INR {v['convenience_fee']}"
    )

ranking = CanonicalPricer.compute_dispersion_ranking(priced)
print("\nPlatform Dispersion & Fee Rankings:")
for r in ranking["platform_rankings"]:
    print(
        f"  - {r['source_name']}: WinRate={r['cheapest_win_rate_pct']}%, AvgFee=INR {r['average_convenience_fee']}"
    )
