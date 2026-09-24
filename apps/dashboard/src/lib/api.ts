/** Client helper for the Observatory API with resilient fallback data. */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function fetchFromApi<T>(endpoint: string): Promise<T | null>;
export function fetchFromApi<T>(endpoint: string, fallback: T): Promise<T>;
export async function fetchFromApi<T>(endpoint: string, fallback?: T): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return fallback !== undefined ? fallback : null;
    return await res.json();
  } catch (err) {
    console.warn(`[API] Could not fetch ${endpoint}:`, err);
    return fallback !== undefined ? fallback : null;
  }
}

export interface IndexResponse {
  index_series: string;
  index_type: string;
  lead_time_days: number;
  index_value: number;
  daily_change_pct: number | null;
  weekly_change_pct: number | null;
  monthly_change_pct: number | null;
  coverage_rate: number;
  is_low_coverage: boolean;
  period_start: string;
  active_version: string;
  // NSO-standard uncertainty around the point estimate
  standard_error?: number | null;
  index_ci_lower?: number | null;
  index_ci_upper?: number | null;
  bootstrap_replications?: number | null;
  variance_method?: string | null;
}

export interface TimeseriesPoint {
  date: string;
  index_value: number;
  daily_change_pct: number | null;
  coverage_rate: number;
}

export interface CorridorItem {
  id: number;
  route_code: string;
  origin: string;
  destination: string;
  origin_airport: string;
  destination_airport: string;
  corridor_type: string;
  dgca_weight: number;
  current_index: number | null;
  daily_change_pct: number | null;
  weekly_change_pct: number | null;
  monthly_change_pct: number | null;
  representative_price: number | null;
}

export interface RouteDetailResponse {
  route_code: string;
  origin: string;
  destination: string;
  corridor_type: string;
  weight_pct: number;
  representative_price: number | null;
  fare_decomposition: {
    base_fare: number;
    fuel_surcharge: number;
    gst_taxes: number;
    udf_adf: number;
    convenience_fee: number;
    total_consumer_fare: number;
  } | null;
  carrier_breakdown: Array<{
    carrier: string;
    name: string;
    basic_fare: number;
    flexi_fare: number;
    is_min: boolean;
    flights: number;
  }>;
}

// =====================================================================
// Forecast Types
// =====================================================================

export interface ForecastPoint {
  target_date: string;
  horizon: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  model_confidence: number;
  component_forecasts: Record<string, { p10: number; p50: number; p90: number }>;
}

export interface ForecastResponse {
  series: string;
  index_type: string;
  forecast_date: string;
  horizon_days: number;
  points: ForecastPoint[];
  ensemble_weights: Record<string, number>;
  model_versions: Record<string, string>;
  generated_at: string;
}

export interface ForecastAllResponse {
  forecasts: Record<string, Record<string, ForecastResponse>>;
  generated_at: string;
}

export interface HistoryAndForecastPoint {
  date: string;
  value?: number;
  p10?: number;
  p25?: number;
  p50?: number;
  p75?: number;
  p90?: number;
  model_confidence?: number;
  standard_error?: number;
  ci_lower?: number;
  ci_upper?: number;
  type: "observed" | "forecast";
}

export interface HistoryAndForecastResponse {
  series: string;
  index_type: string;
  horizon_days: number;
  history: HistoryAndForecastPoint[];
  forecast: HistoryAndForecastPoint[];
  ensemble_weights: Record<string, number>;
  model_versions: Record<string, string>;
  generated_at: string;
}

export interface ForecastAccuracyByHorizon {
  horizon_bucket: string;
  count: number;
  mae: number;
  rmse: number;
  mape_pct: number;
  bias: number;
}

export interface ForecastAccuracyPoint {
  target_date: string;
  generated_at: string | null;
  horizon_days: number;
  actual: number;
  p10: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  p90: number | null;
  model_confidence: number | null;
}

export interface ForecastAccuracyItem {
  series: string;
  index_type: string;
  available: boolean;
  snapshot_count: number;
  matched_count: number;
  mae: number;
  rmse: number;
  mape_pct: number;
  bias: number;
  p50_hit_rate_pct: number;
  p10_p90_coverage_pct: number;
  by_horizon: ForecastAccuracyByHorizon[];
  recent: ForecastAccuracyPoint[];
}

export interface ForecastAccuracyResponse {
  generated_at: string;
  lookback_days: number;
  results: ForecastAccuracyItem[];
}

export interface LeadTimeAnalyticsResponse {
  route_code: string;
  surge_multiplier: number | null;
  lead_time_curve: Array<{
    advance_days: number;
    horizon: string;
    price: number | null;
    label: string;
  }>;
  carrier_escalations: Array<{
    carrier: string;
    surge_multiplier: number;
  }>;
}

export interface DataQualityResponse {
  quote_capture_rate_pct: number;
  valid_quotes_count: number;
  real_life_quotes_count: number;
  synthetic_baseline_count: number;
  carrier_direct_quotes_count: number;
  rpc_fallback_quotes_count: number;
  real_life_share_pct: number;
  rejected_quotes_count: number;
  parser_warnings_count: number;
  deduplicated_quotes_count: number;
  score_distribution: Array<{
    bracket: string;
    percentage: number;
  }>;
}

export interface CrossFeedAuditResponse {
  total_audits: number;
  carrier_direct_count: number;
  rpc_fallback_count: number;
  exact_parity_count: number;
  aggregator_markup_count: number;
  average_discrepancy_pct: number;
  parity_rate_pct: number;
  audits: Array<{
    id: number;
    route_code: string;
    carrier: string;
    flight_number: string;
    travel_date: string;
    advance_days: number;
    carrier_direct_price: number | null;
    rpc_validator_price: number | null;
    discrepancy_amount: number | null;
    discrepancy_pct: number | null;
    status: string;
    notes: string;
    verified_at: string | null;
  }>;
}

export interface CarrierInflationCard {
  carrier_code: string;
  carrier_name: string;
  index_value: number;
  daily_change_pct: number;
  weekly_change_pct: number;
  monthly_change_pct: number;
  routes_covered: number;
  period_date: string;
}

export interface CarrierInflationResponse {
  horizon: string;
  carrier_inflation_spread: number;
  inflation_leader: string;
  value_leader: string;
  carriers: CarrierInflationCard[];
}

export interface CarrierTimeseriesPoint {
  date: string;
  [carrierCode: string]: number | string;
}

export interface VolatilityCorridor {
  route_id: number;
  route_code: string;
  origin: string;
  destination: string;
  corridor_type: string;
  calculation_date: string;
  horizon_days: number;
  min_price: number;
  max_price: number;
  mean_price: number;
  median_price: number;
  spread_pct: number;
  std_dev: number;
  volatility_status: "CALM" | "MODERATE" | "HIGH_VOLATILITY" | "SURGE_ALERT";
  sample_size: number;
}

export interface VolatilityResponse {
  monitored_corridors_count: number;
  average_network_spread_pct: number;
  active_surge_corridors_count: number;
  surge_routes: string[];
  corridors: VolatilityCorridor[];
}

export interface RouteTrajectoryResponse {
  route_code: string;
  origin: string;
  destination: string;
  quotes_count: number;
  quotes: Array<{
    flight_number: string;
    carrier_code: string;
    carrier_name: string;
    base_fare: number;
    total_fare: number;
    advance_purchase_days: number;
    search_timestamp: string;
    fare_family: string;
  }>;
}

export interface OTAPlatformPrice {
  source_name: string;
  source_domain: string;
  base_fare: number;
  taxes_and_fees: number;
  convenience_fee: number;
  promotional_discount: number;
  total_fare: number;
  is_cheapest: boolean;
  markup_vs_direct: number;
}

export interface OTACommonFlight {
  flight_number: string;
  carrier_code: string;
  carrier_name: string;
  origin_airport: string;
  destination_airport: string;
  travel_date: string;
  departure_time: string;
  arrival_time: string;
  canonical_median_fare: number;
  min_walkaway_fare: number;
  max_observed_fare: number;
  carrier_direct_fare: number | null;
  spread_inr: number;
  spread_pct: number;
  cheapest_source: string;
  sources_count: number;
  platform_matrix: Record<string, OTAPlatformPrice>;
}

export interface OTACommonFlightsResponse {
  route_code: string;
  horizon_days: number;
  travel_date: string;
  total_quotes_scraped: number;
  carrier_quotes_count: number;
  common_flights_count: number;
  common_flights: OTACommonFlight[];
}

export interface OTAPlatformRanking {
  source_name: string;
  domain: string;
  quotes_count: number;
  cheapest_win_rate_pct: number;
  average_convenience_fee: number;
  average_markup_over_direct: number;
}

export interface OTADispersionRankingResponse {
  total_flights_analyzed: number;
  route_code: string;
  horizon_days: number;
  platform_rankings: OTAPlatformRanking[];
}

export interface MarketBriefingData {
  timestamp: string;
  headline: {
    index_value: number;
    daily_change_pct: number | null;
    weekly_change_pct: number | null;
    monthly_change_pct: number | null;
    vs_base_pct: number;
    period_date: string;
    anchor_horizon: string;
  };
  carrier_power: {
    inflation_leader: string;
    inflation_leader_code: string;
    inflation_leader_index: number;
    inflation_leader_change_pct: number;
    value_leader: string;
    value_leader_code: string;
    value_leader_index: number;
    value_leader_min_fare: number;
    carrier_spread_pts: number;
    carriers: Array<{
      carrier_code: string;
      carrier_name: string;
      index_value: number;
      daily_change_pct: number;
      routes_covered: number;
    }>;
  };
  volatility: {
    average_network_spread_pct: number;
    active_surge_corridors_count: number;
    monitored_corridors_count: number;
    top_surge_corridors: Array<{
      route_code: string;
      city_pair: string;
      origin: string;
      destination: string;
      corridor_type: string;
      spread_pct: number;
      min_price: number;
      max_price: number;
      median_price: number;
      volatility_status: string;
    }>;
  };
  lead_time: {
    surge_multiplier: number;
    t1_price: number;
    t7_price: number;
    t15_price: number;
    t30_price: number;
    t45_price: number;
    t30_savings_pct: number;
    t45_savings_pct: number;
  };
  narrative: {
    retail_context: string;
    carrier_summary: string;
    elasticity_summary: string;
    microstructure: string;
    monetary_policy: string;
  };
}

