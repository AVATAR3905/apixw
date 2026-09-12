"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { 
  TrendingUp, 
  Clock, 
  BarChart3, 
  Fuel, 
  Scale, 
  Plane, 
  AlertTriangle, 
  ArrowUpDown, 
  Calendar, 
  Layers, 
  CheckCircle2,
  ShieldAlert,
  Globe,
  Building2,
  ExternalLink
} from "lucide-react";
import Link from "next/link";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { LineChart, SeriesConfig } from "@/components/charts/LineChart";
import { 
  fetchFromApi, 
  CarrierInflationResponse, 
  CarrierTimeseriesPoint, 
  CorridorItem,
  LeadTimeAnalyticsResponse,
  VolatilityResponse,
  RouteTrajectoryResponse,
  OTADispersionRankingResponse,
  OTAPlatformRanking
} from "@/lib/api";

function MarketDynamicsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const tabParam = searchParams.get("tab");
  const [activeTab, setActiveTab] = useState<"carriers" | "lead-time" | "volatility" | "fuel" | "ota-dispersion">(
    tabParam === "carriers" || tabParam === "lead-time" || tabParam === "volatility" || tabParam === "fuel" || tabParam === "ota-dispersion"
      ? tabParam
      : "carriers"
  );

  useEffect(() => {
    if (tabParam && (tabParam === "carriers" || tabParam === "lead-time" || tabParam === "volatility" || tabParam === "fuel" || tabParam === "ota-dispersion")) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const switchTab = (tab: "carriers" | "lead-time" | "volatility" | "fuel" | "ota-dispersion") => {
    setActiveTab(tab);
    router.replace(`/market-dynamics?tab=${tab}`, { scroll: false });
  };

  // -------------------------------------------------------------
  // TAB 1: CARRIER-WISE INFLATION STATE
  // -------------------------------------------------------------
  const [carrierHorizon, setCarrierHorizon] = useState<number>(15);
  const [inflationData, setInflationData] = useState<CarrierInflationResponse | null>(null);
  const [carrierTimeseries, setCarrierTimeseries] = useState<CarrierTimeseriesPoint[]>([]);
  const [carrierCorridors, setCarrierCorridors] = useState<CorridorItem[]>([]);
  const [carrierLoading, setCarrierLoading] = useState<boolean>(true);

  useEffect(() => {
    if (activeTab !== "carriers") return;
    async function loadCarrierData() {
      setCarrierLoading(true);
      const [inf, ts, rts] = await Promise.all([
        fetchFromApi<CarrierInflationResponse>(`/analytics/carrier-inflation?horizon=${carrierHorizon}`),
        fetchFromApi<CarrierTimeseriesPoint[]>(`/analytics/carrier-inflation/timeseries?horizon=${carrierHorizon}`),
        fetchFromApi<CorridorItem[]>("/routes"),
      ]);
      if (inf) setInflationData(inf);
      if (ts) setCarrierTimeseries(ts);
      if (rts) setCarrierCorridors(rts);
      setCarrierLoading(false);
    }
    loadCarrierData();
  }, [activeTab, carrierHorizon]);

  const chartSeries: SeriesConfig[] = [
    { key: "6E", name: "IndiGo (6E)", color: "#38bdf8", strokeWidth: 2.5 },
    { key: "AI", name: "Air India (AI)", color: "#f97316", strokeWidth: 2.5 },
    { key: "SG", name: "SpiceJet (SG)", color: "#f59e0b", strokeWidth: 2 },
    { key: "QP", name: "Akasa Air (QP)", color: "#a855f7", strokeWidth: 2 },
  ];

  // -------------------------------------------------------------
  // TAB 2: LEAD-TIME DYNAMICS STATE
  // -------------------------------------------------------------
  const [selectedLeadRoute, setSelectedLeadRoute] = useState("DEL-BOM");
  const [leadRoutes, setLeadRoutes] = useState<Array<{ code: string; name: string }>>([
    { code: "DEL-BOM", name: "Delhi ↔ Mumbai" },
    { code: "DEL-BLR", name: "Delhi ↔ Bengaluru" },
    { code: "BOM-BLR", name: "Mumbai ↔ Bengaluru" },
    { code: "DEL-CCU", name: "Delhi ↔ Kolkata" },
    { code: "DEL-IXS", name: "Delhi ↔ Silchar (Regional)" },
  ]);
  const [leadTimeData, setLeadTimeData] = useState<LeadTimeAnalyticsResponse>({
    route_code: "DEL-BOM",
    surge_multiplier: 2.04,
    lead_time_curve: [
      { advance_days: 45, horizon: "T+45", price: 3000, label: "Early Bird" },
      { advance_days: 30, horizon: "T+30", price: 3240, label: "Advance Planning" },
      { advance_days: 15, horizon: "T+15", price: 3750, label: "Headline Anchor" },
      { advance_days: 7, horizon: "T+7", price: 4800, label: "Short Planning" },
      { advance_days: 1, horizon: "T+1", price: 6120, label: "Departure Eve" },
    ],
    carrier_escalations: [],
  });

  useEffect(() => {
    if (activeTab !== "lead-time") return;
    async function loadLeadTimeRoutes() {
      const corridors = await fetchFromApi<CorridorItem[]>("/routes", []);
      if (corridors && corridors.length > 0) {
        setLeadRoutes(
          corridors.map((c) => ({
            code: c.route_code,
            name: `${c.origin} ↔ ${c.destination}`,
          }))
        );
      }
    }
    loadLeadTimeRoutes();
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== "lead-time") return;
    async function loadCurve() {
      const data = await fetchFromApi<LeadTimeAnalyticsResponse>(
        `/lead-time?route_code=${selectedLeadRoute}`,
        leadTimeData
      );
      if (data) setLeadTimeData(data);
    }
    loadCurve();
  }, [activeTab, selectedLeadRoute]);

  // -------------------------------------------------------------
  // TAB 3: VOLATILITY RADAR STATE
  // -------------------------------------------------------------
  const [volatilityHorizon, setVolatilityHorizon] = useState<number>(15);
  const [volatilityData, setVolatilityData] = useState<VolatilityResponse | null>(null);
  const [selectedVolRoute, setSelectedVolRoute] = useState<string>("DEL-BOM");
  const [volRouteQuotes, setVolRouteQuotes] = useState<RouteTrajectoryResponse | null>(null);
  const [volatilityLoading, setVolatilityLoading] = useState<boolean>(true);

  useEffect(() => {
    if (activeTab !== "volatility") return;
    async function loadVolData() {
      setVolatilityLoading(true);
      const res = await fetchFromApi<VolatilityResponse>(`/analytics/volatility?horizon=${volatilityHorizon}`);
      if (res) {
        setVolatilityData(res);
        if (res.corridors.length > 0 && !selectedVolRoute) {
          setSelectedVolRoute(res.corridors[0].route_code);
        }
      }
      setVolatilityLoading(false);
    }
    loadVolData();
  }, [activeTab, volatilityHorizon]);

  useEffect(() => {
    if (activeTab !== "volatility" || !selectedVolRoute) return;
    async function loadRouteQuotes() {
      const res = await fetchFromApi<RouteTrajectoryResponse>(`/analytics/volatility/${selectedVolRoute}`);
      if (res) setVolRouteQuotes(res);
    }
    loadRouteQuotes();
  }, [activeTab, selectedVolRoute]);

  // -------------------------------------------------------------
  // TAB 4: FUEL CONTEXT STATE
  // -------------------------------------------------------------
  const defaultFuelSeries = [
    { date: "01 Aug", atf: 94200, atfIndex: 100.0, fareIndex: 100.0 },
    { date: "07 Aug", atf: 94500, atfIndex: 100.3, fareIndex: 101.8 },
    { date: "14 Aug", atf: 95100, atfIndex: 101.0, fareIndex: 103.4 },
    { date: "21 Aug", atf: 96200, atfIndex: 102.1, fareIndex: 105.8 },
    { date: "28 Aug", atf: 97800, atfIndex: 103.8, fareIndex: 108.4 },
  ];
  const [fuelSeries, setFuelSeries] = useState(defaultFuelSeries);
  const [fuelReport, setFuelReport] = useState<any>(null);

  useEffect(() => {
    if (activeTab !== "fuel") return;
    async function loadFuel() {
      const data = await fetchFromApi<any>("/fuel-context?location=Delhi", null);
      if (data) setFuelReport(data);
    }
    loadFuel();
  }, [activeTab]);

  // -------------------------------------------------------------
  // TAB 5: INTER-OTA DISPERSION STATE
  // -------------------------------------------------------------
  const [otaRoute, setOtaRoute] = useState<string>("DEL-BOM");
  const [otaHorizon, setOtaHorizon] = useState<number>(15);
  const [otaDispersion, setOtaDispersion] = useState<OTADispersionRankingResponse | null>(null);
  const [sourcesStatus, setSourcesStatus] = useState<any>(null);
  const [otaLoading, setOtaLoading] = useState<boolean>(false);

  useEffect(() => {
    if (activeTab !== "ota-dispersion") return;
    async function loadOtaData() {
      setOtaLoading(true);
      const [disp, status] = await Promise.all([
        fetchFromApi<OTADispersionRankingResponse>(`/ota/dispersion-ranking?route_code=${otaRoute}&horizon=${otaHorizon}`),
        fetchFromApi<any>("/ota/sources-status"),
      ]);
      if (disp) setOtaDispersion(disp);
      if (status) setSourcesStatus(status);
      setOtaLoading(false);
    }
    loadOtaData();
  }, [activeTab, otaRoute, otaHorizon]);

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <SectionHeader
        title="Phoenix Market Dynamics Matrix"
        headline="Analytical suite exploring airline pricing power, advance-booking yield curves, intraday volatility spreads, and jet fuel cost pass-through."
        badge="PHOENIX YIELD INTELLIGENCE"
        badgeVariant="solid"
      />

      {/* Tabs Navigation Bar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-hairline/60 pb-3">
        <button
          onClick={() => switchTab("carriers")}
          className={`flex items-center gap-2 rounded-[14px] px-4 py-2 text-xs font-sans font-medium transition-all ${
            activeTab === "carriers"
              ? "bg-flame-500/20 text-flame-400 border border-flame-500/40 shadow-glow-flame"
              : "bg-surface/70 text-mid-gray hover:text-ink hover:bg-surface-alt/70 border border-hairline/40"
          }`}
        >
          <TrendingUp className="h-3.5 w-3.5" />
          <span>Carrier-Wise Inflation</span>
        </button>

        <button
          onClick={() => switchTab("lead-time")}
          className={`flex items-center gap-2 rounded-[14px] px-4 py-2 text-xs font-sans font-medium transition-all ${
            activeTab === "lead-time"
              ? "bg-flame-500/20 text-flame-400 border border-flame-500/40 shadow-glow-flame"
              : "bg-surface/70 text-mid-gray hover:text-ink hover:bg-surface-alt/70 border border-hairline/40"
          }`}
        >
          <Clock className="h-3.5 w-3.5" />
          <span>Advance Booking Elasticity (T+1..T+45)</span>
        </button>

        <button
          onClick={() => switchTab("volatility")}
          className={`flex items-center gap-2 rounded-[14px] px-4 py-2 text-xs font-sans font-medium transition-all ${
            activeTab === "volatility"
              ? "bg-flame-500/20 text-flame-400 border border-flame-500/40 shadow-glow-flame"
              : "bg-surface/70 text-mid-gray hover:text-ink hover:bg-surface-alt/70 border border-hairline/40"
          }`}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          <span>Intraday Volatility Radar</span>
        </button>

        <button
          onClick={() => switchTab("fuel")}
          className={`flex items-center gap-2 rounded-[14px] px-4 py-2 text-xs font-sans font-medium transition-all ${
            activeTab === "fuel"
              ? "bg-flame-500/20 text-flame-400 border border-flame-500/40 shadow-glow-flame"
              : "bg-surface/70 text-mid-gray hover:text-ink hover:bg-surface-alt/70 border border-hairline/40"
          }`}
        >
          <Fuel className="h-3.5 w-3.5" />
          <span>Aviation Fuel (ATF) Overlay</span>
        </button>

        <button
          onClick={() => switchTab("ota-dispersion")}
          className={`flex items-center gap-2 rounded-[14px] px-4 py-2 text-xs font-sans font-medium transition-all ${
            activeTab === "ota-dispersion"
              ? "bg-flame-500/20 text-flame-400 border border-flame-500/40 shadow-glow-flame"
              : "bg-surface/70 text-mid-gray hover:text-ink hover:bg-surface-alt/70 border border-hairline/40"
          }`}
        >
          <Globe className="h-3.5 w-3.5" />
          <span>Inter-OTA Price Dispersion</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: CARRIER-WISE INFLATION CONTENT */}
      {/* ========================================================================= */}
      {activeTab === "carriers" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink font-sans">
                Airline Price Indices (CPI-Carrier)
              </h3>
              <p className="text-xs text-mid-gray font-sans">
                Independent Laspeyres trajectories tracking pricing power of IndiGo, Air India, SpiceJet, and Akasa Air.
              </p>
            </div>

            <div className="flex items-center gap-1 rounded-[18px] border border-hairline bg-canvas p-1 self-start sm:self-auto">
              <span className="text-[11px] font-mono text-mid-gray px-2">Booking Horizon:</span>
              {([1, 7, 15, 30, 45] as const).map((h) => (
                <button
                  key={h}
                  onClick={() => setCarrierHorizon(h)}
                  className={`rounded-[18px] px-3 py-1 text-xs font-sans font-medium transition-all ${
                    carrierHorizon === h
                      ? "bg-ink text-paper shadow-subtle"
                      : "text-mid-gray hover:text-ink"
                  }`}
                >
                  T+{h}
                </button>
              ))}
            </div>
          </div>

          {/* Stat Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Inter-Airline Spread"
              value={inflationData ? `${inflationData.carrier_inflation_spread.toFixed(1)} pts` : "8.4 pts"}
              subtitle="Max - Min airline price index delta"
              icon={Scale}
              badge="Price Dispersion"
              badgeVariant="neutral"
            />
            <StatCard
              title="Inflation Pace Leader"
              value={inflationData?.inflation_leader || "IndiGo (6E)"}
              subtitle="Highest relative price increase vs base"
              icon={TrendingUp}
              badge="Yield Escalator"
              badgeVariant="warning"
            />
            <StatCard
              title="Value Leader"
              value={inflationData?.value_leader || "Akasa Air (QP)"}
              subtitle="Most competitive entry fares"
              icon={Plane}
              badge="Lowest Baseline"
              badgeVariant="safe"
            />
            <StatCard
              title="Tracked Carrier Basket"
              value="4 Major Airlines"
              subtitle="Covers >92% domestic seat capacity"
              icon={Layers}
              badge="Scheduled Fleet"
              badgeVariant="neutral"
            />
          </div>

          {/* Time Series Chart */}
          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-ink" />
                <span className="font-semibold text-xs text-ink font-sans">
                  30-DAY AIRLINE PRICE TRAJECTORIES (T+{carrierHorizon} HORIZON)
                </span>
              </div>
              <span className="text-[11px] text-mid-gray font-sans">Normalized: 2026-08-01 = 100.00</span>
            </div>

            <LineChart
              data={carrierTimeseries.length > 0 ? carrierTimeseries : [
                { date: "01 Aug", "6E": 100.0, "AI": 100.0, "SG": 100.0, "QP": 100.0 },
                { date: "08 Aug", "6E": 102.1, "AI": 101.4, "SG": 99.8, "QP": 99.2 },
                { date: "15 Aug", "6E": 104.8, "AI": 103.2, "SG": 100.5, "QP": 99.8 },
                { date: "22 Aug", "6E": 107.4, "AI": 105.1, "SG": 101.2, "QP": 100.4 },
                { date: "29 Aug", "6E": 109.8, "AI": 106.8, "SG": 102.1, "QP": 101.2 },
              ]}
              xKey="date"
              series={chartSeries}
              height={260}
              yDomain={[98, 112]}
              valuePrefix="Index: "
            />
          </div>

          {/* Carrier Breakdown Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { code: "6E", name: "IndiGo", idx: "109.8", d7: "+2.8%", routes: "10/10", tag: "Market Leader (62% Share)", variant: "danger" as const },
              { code: "AI", name: "Air India", idx: "106.8", d7: "+1.9%", routes: "10/10", tag: "Full-Service Hybrid", variant: "warning" as const },
              { code: "SG", name: "SpiceJet", idx: "102.1", d7: "+0.8%", routes: "6/10", tag: "Regional Tiering", variant: "safe" as const },
              { code: "QP", name: "Akasa Air", idx: "101.2", d7: "+0.6%", routes: "8/10", tag: "Ultra-Competitive", variant: "safe" as const },
            ].map((c) => (
              <div key={c.code} className="rounded-cards border border-hairline bg-paper p-4 shadow-subtle space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-ink">{c.name} ({c.code})</span>
                  <Badge variant={c.variant} size="xs">{c.d7} 7D</Badge>
                </div>
                <div className="flex items-baseline justify-between">
                  <span className="text-3xl font-bold font-sans text-ink tracking-tight">{c.idx}</span>
                  <span className="text-[11px] font-mono text-ink-soft">{c.routes} Corridors</span>
                </div>
                <div className="text-[11px] text-ink-soft font-sans border-t border-hairline pt-2">
                  {c.tag}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: LEAD-TIME DYNAMICS CONTENT */}
      {/* ========================================================================= */}
      {activeTab === "lead-time" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink font-sans">
                Advance Booking Elasticity Curves (T+45 to T+1)
              </h3>
              <p className="text-xs text-mid-gray font-sans">
                Observing the price surge curve across advance-purchase windows to isolate yield management escalations.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-sans text-mid-gray">Select Corridor:</span>
              <select
                value={selectedLeadRoute}
                onChange={(e) => setSelectedLeadRoute(e.target.value)}
                className="rounded-[18px] border border-hairline bg-canvas px-3 py-1.5 text-xs font-sans text-ink cursor-pointer focus:outline-none focus:border-ink"
              >
                {leadRoutes.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.code} — {r.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Lead Time Stat Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Surge Multiplier (T+45 to T+1)"
              value={`${leadTimeData.surge_multiplier?.toFixed(2) || "2.04"}x`}
              subtitle="Departure Eve vs Early Bird multiplier"
              icon={ArrowUpDown}
              badge="Yield Surge"
              badgeVariant="warning"
            />
            <StatCard
              title="T+15 Macro Anchor Fare"
              value={`₹${(leadTimeData.lead_time_curve.find((c) => c.horizon === "T+15")?.price || 3750).toLocaleString()}`}
              subtitle="Insulated official index baseline"
              icon={ShieldAlert}
              badge="Official Standard"
              badgeVariant="neutral"
            />
            <StatCard
              title="T+1 Peak Distress Fare"
              value={`₹${(leadTimeData.lead_time_curve.find((c) => c.horizon === "T+1")?.price || 6120).toLocaleString()}`}
              subtitle="Emergency & last-minute bookings"
              icon={AlertTriangle}
              badge="Peak Yield"
              badgeVariant="danger"
            />
            <StatCard
              title="Advance Planning Savings"
              value="51.2% Savings"
              subtitle="By booking 30+ days ahead"
              icon={CheckCircle2}
              badge="Consumer Sweet Spot"
              badgeVariant="safe"
            />
          </div>

          {/* Horizon Breakdown Strip */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            {leadTimeData.lead_time_curve.map((item) => {
              const baseP = leadTimeData.lead_time_curve[0]?.price || 3000;
              const mult = item.price && baseP > 0 ? (item.price / baseP).toFixed(2) : "1.00";
              const isAnchor = item.horizon === "T+15";
              const isSafe = item.horizon === "T+45" || item.horizon === "T+30";
              const isWarning = item.horizon === "T+7";

              const badgeVariant = isAnchor 
                ? ("solid" as const) 
                : isSafe 
                ? ("safe" as const) 
                : isWarning 
                ? ("warning" as const) 
                : ("danger" as const);

              const borderClass = isAnchor
                ? "border-ink bg-surface-alt ring-1 ring-hairline"
                : isSafe
                ? "border-emerald-200/70 bg-emerald-50/20"
                : isWarning
                ? "border-amber-200/70 bg-amber-50/20"
                : "border-red-200/70 bg-red-50/20";

              return (
                <div
                  key={item.horizon}
                  className={`rounded-cards border p-4 shadow-subtle transition-all ${borderClass}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-ink">{item.horizon}</span>
                    <Badge variant={badgeVariant} size="xs">
                      {isAnchor ? "OFFICIAL ANCHOR" : item.label}
                    </Badge>
                  </div>
                  <div className="mt-3">
                    <span className="text-2xl font-bold font-sans text-ink tracking-tight">
                      ₹{item.price ? item.price.toLocaleString() : "—"}
                    </span>
                    <div className="mt-1 flex items-center justify-between text-[11px] font-mono text-ink-soft">
                      <span>Multiplier:</span>
                      <span className="font-semibold text-ink">{mult}x</span>
                    </div>
                  </div>
                  <p className="mt-2 text-[11px] text-mid-gray font-sans border-t border-hairline pt-1.5">
                    {item.advance_days} days prior to travel date.
                  </p>
                </div>
              );
            })}
          </div>

          {/* Lead-Time Curve Chart */}
          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-xs text-ink font-sans flex items-center gap-2">
                <Clock className="h-4 w-4 text-ink" />
                ADVANCE PURCHASE PRICE ESCALATION CURVE — {selectedLeadRoute}
              </span>
              <span className="text-[11px] text-mid-gray font-sans">Representative Route Median (₹)</span>
            </div>

            <LineChart
              data={leadTimeData.lead_time_curve.map((c) => ({
                horizon: c.horizon,
                fare: c.price || 3000,
              }))}
              xKey="horizon"
              series={[{ key: "fare", name: "Observed Fare (₹)", color: "#f97316", strokeWidth: 2.5 }]}
              height={250}
              valuePrefix="Fare: ₹"
            />
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: VOLATILITY RADAR CONTENT */}
      {/* ========================================================================= */}
      {activeTab === "volatility" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink font-sans">
                Intraday Fare Dispersion & Surge Radar
              </h3>
              <p className="text-xs text-mid-gray font-sans">
                Monitoring spread volatility ((Max - Min) / Mean) and price velocity across domestic corridors.
              </p>
            </div>

            <div className="flex items-center gap-1 rounded-[18px] border border-hairline bg-canvas p-1 self-start sm:self-auto">
              <span className="text-[11px] font-mono text-mid-gray px-2">Horizon:</span>
              {([1, 7, 15, 30, 45] as const).map((h) => (
                <button
                  key={h}
                  onClick={() => setVolatilityHorizon(h)}
                  className={`rounded-[18px] px-3 py-1 text-xs font-sans font-medium transition-all ${
                    volatilityHorizon === h
                      ? "bg-ink text-paper shadow-subtle"
                      : "text-mid-gray hover:text-ink"
                  }`}
                >
                  T+{h}
                </button>
              ))}
            </div>
          </div>

          {/* Volatility Stat Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Average Network Spread"
              value={`${volatilityData?.average_network_spread_pct.toFixed(1) || "29.5"}%`}
              subtitle="Mean (Max - Min) / Mean across 10 routes"
              icon={ArrowUpDown}
              badge="Intraday Spread"
              badgeVariant="neutral"
            />
            <StatCard
              title="Active Surge Corridors"
              value={`${volatilityData?.active_surge_corridors_count || 3} of 10`}
              subtitle="Routes exhibiting >35% intraday spread"
              icon={AlertTriangle}
              badge="Surge Alerts"
              badgeVariant="warning"
            />
            <StatCard
              title="Highest Volatility Sector"
              value={volatilityData?.corridors[0]?.route_code || "DEL-IXS (Silchar)"}
              subtitle="Constrained capacity regional corridor"
              icon={TrendingUp}
              badge="Thin Market"
              badgeVariant="danger"
            />
            <StatCard
              title="Most Stable Trunk Corridor"
              value="DEL-BOM (Mumbai)"
              subtitle="High carrier competition minimizes swings"
              icon={CheckCircle2}
              badge="Trunk Metro"
              badgeVariant="safe"
            />
          </div>

          {/* Volatility Corridor Table */}
          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-xs text-ink font-sans">
                CORRIDOR VOLATILITY & INTRADAY DISPERSION MATRIX (T+{volatilityHorizon})
              </span>
              <span className="text-[11px] text-mid-gray font-sans">Live Quote Aggregation</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-hairline text-mid-gray font-sans uppercase tracking-[0.6px] text-[11px]">
                    <th className="pb-3 font-medium">Corridor</th>
                    <th className="pb-3 font-medium">Classification</th>
                    <th className="pb-3 font-medium">Min Fare</th>
                    <th className="pb-3 font-medium">Median Fare</th>
                    <th className="pb-3 font-medium">Max Fare</th>
                    <th className="pb-3 font-medium">Spread %</th>
                    <th className="pb-3 font-medium text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline font-sans">
                  {(volatilityData?.corridors && volatilityData.corridors.length > 0 ? volatilityData.corridors : [
                    { route_code: "DEL-IXS", origin: "Delhi", destination: "Silchar", corridor_type: "REGIONAL_THIN", min_price: 4800, median_price: 6200, max_price: 9400, spread_pct: 44.2, volatility_status: "SURGE_ALERT" },
                    { route_code: "DEL-DHM", origin: "Delhi", destination: "Dharamshala", corridor_type: "REGIONAL_THIN", min_price: 4200, median_price: 5400, max_price: 7800, spread_pct: 38.6, volatility_status: "SURGE_ALERT" },
                    { route_code: "DEL-BOM", origin: "Delhi", destination: "Mumbai", corridor_type: "METRO_TRUNK", min_price: 2868, median_price: 3750, max_price: 5200, spread_pct: 26.4, volatility_status: "MODERATE" },
                    { route_code: "DEL-BLR", origin: "Delhi", destination: "Bengaluru", corridor_type: "METRO_TRUNK", min_price: 3200, median_price: 4100, max_price: 5600, spread_pct: 24.8, volatility_status: "MODERATE" },
                    { route_code: "BOM-BLR", origin: "Mumbai", destination: "Bengaluru", corridor_type: "METRO_TRUNK", min_price: 2600, median_price: 3200, max_price: 4100, spread_pct: 21.2, volatility_status: "CALM" },
                  ]).map((c: any) => (
                    <tr key={c.route_code} className="hover:bg-canvas transition-colors">
                      <td className="py-3">
                        <div className="font-mono font-semibold text-ink">{c.route_code}</div>
                        <div className="text-[11px] text-ink-soft font-sans">{c.origin} ↔ {c.destination}</div>
                      </td>
                      <td className="py-3">
                        <Badge variant={c.corridor_type === "METRO_TRUNK" ? "neutral" : "warning"} size="xs">
                          {c.corridor_type === "METRO_TRUNK" ? "Trunk Metro" : "Regional Thin"}
                        </Badge>
                      </td>
                      <td className="py-3 font-mono">₹{c.min_price?.toLocaleString()}</td>
                      <td className="py-3 font-mono font-bold text-ink">₹{c.median_price?.toLocaleString()}</td>
                      <td className="py-3 font-mono">₹{c.max_price?.toLocaleString()}</td>
                      <td className="py-3 font-mono font-bold text-ink">{c.spread_pct?.toFixed(1)}%</td>
                      <td className="py-3 text-right">
                        <Badge variant={c.volatility_status === "SURGE_ALERT" ? "danger" : c.volatility_status === "CALM" ? "safe" : "warning"} size="xs">
                          {c.volatility_status.replace("_", " ")}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: FUEL CONTEXT CONTENT */}
      {/* ========================================================================= */}
      {activeTab === "fuel" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink font-sans">
                Aviation Turbine Fuel (ATF) Explanatory Macro Overlay
              </h3>
              <p className="text-xs text-mid-gray font-sans">
                Tracking monthly state oil marketing company (IOCL) jet fuel spot revisions alongside consumer airfares.
              </p>
            </div>

            <div className="flex items-center gap-2 font-mono text-xs text-ink bg-canvas px-3 py-1.5 rounded-[18px] border border-hairline">
              <Fuel className="h-4 w-4 text-ink" />
              <span>~38% Airline Operating Cost Share</span>
            </div>
          </div>

          {/* Fuel Benchmark Banner */}
          <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
              <div className="space-y-2 max-w-2xl">
                <span className="font-mono text-xs font-semibold uppercase tracking-wider text-mid-gray">
                  IOCL DELHI JET FUEL BENCHMARK
                </span>
                <div className="flex items-baseline gap-4">
                  <span className="text-5xl sm:text-6xl font-semibold tracking-tight text-ink font-sans">
                    ₹97,800
                  </span>
                  <div className="flex flex-col">
                    <Badge variant="warning" size="xs">
                      +3.82% Monthly Revision
                    </Badge>
                    <span className="text-xs text-mid-gray font-mono mt-1">Per kilolitre (IOCL Delhi domestic)</span>
                  </div>
                </div>
                <p className="text-xs text-mid-gray leading-relaxed font-sans mt-2">
                  While ATF represents roughly 38% of Cost per Available Seat Kilometer (CASK), APIX-2.0 treats jet fuel as an <strong className="text-ink">explanatory macroeconomic context</strong> rather than claiming instant 1:1 daily pass-through, due to forward fuel hedging and dynamic yield tiering.
                </p>
              </div>

              <div className="rounded-nested border border-hairline bg-canvas p-4 font-mono text-xs space-y-2 lg:w-72 shrink-0">
                <div className="flex justify-between text-mid-gray">
                  <span>Crude Brent:</span>
                  <span className="text-ink font-semibold">$82.40 / bbl</span>
                </div>
                <div className="flex justify-between text-mid-gray">
                  <span>Central Excise Duty:</span>
                  <span className="text-ink font-semibold">11.0%</span>
                </div>
                <div className="flex justify-between text-mid-gray">
                  <span>State VAT (Delhi):</span>
                  <span className="text-ink font-semibold">25.0%</span>
                </div>
                <div className="flex justify-between text-mid-gray border-t border-hairline pt-1.5">
                  <span>Pass-Through Lag:</span>
                  <span className="text-ink font-semibold">30–60 Days</span>
                </div>
              </div>
            </div>
          </div>

          {/* ATF vs Airfare Chart */}
          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-xs text-ink font-sans flex items-center gap-2">
                <Fuel className="h-4 w-4 text-ink" />
                INDEXED TRAJECTORIES: AIRFARE INDEX VS ATF SPOT RATE
              </span>
              <span className="text-[11px] text-mid-gray font-sans">Baseline: 2026-08-01 = 100.00</span>
            </div>

            <LineChart
              data={fuelSeries}
              xKey="date"
              series={[
                { key: "fareIndex", name: "Headline Airfare Index", color: "#f97316", strokeWidth: 2.5 },
                { key: "atfIndex", name: "ATF Spot Price Index", color: "#38bdf8", strokeWidth: 2, strokeDasharray: "4 4" },
              ]}
              height={260}
              valuePrefix="Index: "
            />
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 5: INTER-OTA DISPERSION & PRICING CONTENT */}
      {/* ========================================================================= */}
      {activeTab === "ota-dispersion" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Controls bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink font-sans">
                Cross-OTA Price Dispersion & Fee Harmonization
              </h3>
              <p className="text-xs text-mid-gray font-sans">
                Real-time price divergence, convenience fees, and walkaway fare reconciliation across Direct Airlines and 6 major OTAs.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Route Selector */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-mid-gray">Corridor:</span>
                <select
                  value={otaRoute}
                  onChange={(e) => setOtaRoute(e.target.value)}
                  className="rounded-[18px] border border-hairline bg-paper px-3 py-1 text-xs font-mono text-ink shadow-subtle focus:outline-none"
                >
                  <option value="DEL-BOM">DEL ↔ BOM (Delhi - Mumbai)</option>
                  <option value="DEL-BLR">DEL ↔ BLR (Delhi - Bengaluru)</option>
                  <option value="BOM-BLR">BOM ↔ BLR (Mumbai - Bengaluru)</option>
                  <option value="DEL-CCU">DEL ↔ CCU (Delhi - Kolkata)</option>
                  <option value="DEL-IXS">DEL ↔ IXS (Silchar Regional)</option>
                </select>
              </div>

              {/* Horizon Selector */}
              <div className="flex items-center gap-1 bg-paper border border-hairline rounded-[18px] p-0.5">
                {[1, 7, 15, 30, 45].map((h) => (
                  <button
                    key={h}
                    onClick={() => setOtaHorizon(h)}
                    className={`rounded-[16px] px-2.5 py-1 text-[11px] font-mono transition-all ${
                      otaHorizon === h
                        ? "bg-ink text-paper font-semibold"
                        : "text-mid-gray hover:text-ink"
                    }`}
                  >
                    T+{h}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              title="INGESTION CHANNELS"
              value="10 Sources"
              subtitle="4 Direct + 6 OTAs"
            />
            <StatCard
              title="BENCHMARK METHOD"
              value="Platform Median"
              subtitle="MoSPI CPI standard"
            />
            <StatCard
              title="CONVENIENCE FEES"
              value="₹0 – ₹420"
              subtitle="Unbundled fee variance"
            />
            <StatCard
              title="FLIGHT MATCHING"
              value="Deterministic"
              subtitle="IATA + Number + Time"
            />
          </div>

          {/* Platform Fee & Dispersion Ranking Table */}
          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-hairline pb-4">
              <div>
                <span className="font-semibold text-xs text-ink font-sans flex items-center gap-2">
                  <Globe className="h-4 w-4 text-ink" />
                  CROSS-PLATFORM DISPERSION & CONVENIENCE FEE AUDIT ({otaRoute}, T+{otaHorizon})
                </span>
                <p className="text-[11px] text-mid-gray font-sans mt-0.5">
                  Comparison of published convenience fees, price divergence, and win rates across direct carriers and OTA aggregators.
                </p>
              </div>
              <Link
                href={`/corridors/${otaRoute}`}
                className="inline-flex items-center gap-1.5 rounded-[18px] bg-canvas border border-hairline px-3 py-1.5 text-xs font-mono text-ink hover:bg-paper hover:border-ink transition-colors shrink-0"
              >
                <span>Inspect Flight Matrix</span>
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>

            {otaLoading ? (
              <div className="p-8 text-center text-xs font-mono text-mid-gray">
                Evaluating real-time cross-OTA price quotes for {otaRoute}...
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-hairline font-mono text-[11px] text-mid-gray">
                      <th className="pb-3 font-medium">PLATFORM / SOURCE</th>
                      <th className="pb-3 font-medium">CHANNEL TYPE</th>
                      <th className="pb-3 font-medium">CONVENIENCE FEE</th>
                      <th className="pb-3 font-medium">DISCOUNT POLICY</th>
                      <th className="pb-3 font-medium">CHEAPEST WIN RATE</th>
                      <th className="pb-3 font-medium">AVG DELTA VS DIRECT</th>
                      <th className="pb-3 font-medium">STATUS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline">
                    {(otaDispersion?.platform_rankings || [
                      { source_name: "Carrier Direct (IndiGo)", domain: "6e.airline.direct", quotes_count: 5, cheapest_win_rate_pct: 35.0, average_convenience_fee: 0.0, average_markup_over_direct: 0.0 },
                      { source_name: "Carrier Direct (Air India)", domain: "ai.airline.direct", quotes_count: 4, cheapest_win_rate_pct: 25.0, average_convenience_fee: 0.0, average_markup_over_direct: 0.0 },
                      { source_name: "Carrier Direct (SpiceJet)", domain: "sg.airline.direct", quotes_count: 4, cheapest_win_rate_pct: 20.0, average_convenience_fee: 0.0, average_markup_over_direct: 0.0 },
                      { source_name: "Carrier Direct (Akasa Air)", domain: "qp.airline.direct", quotes_count: 4, cheapest_win_rate_pct: 20.0, average_convenience_fee: 0.0, average_markup_over_direct: 0.0 },
                      { source_name: "EaseMyTrip", domain: "easemytrip.com", quotes_count: 5, cheapest_win_rate_pct: 0.0, average_convenience_fee: 0.0, average_markup_over_direct: 502.44 },
                      { source_name: "Skyscanner India", domain: "skyscanner.co.in", quotes_count: 5, cheapest_win_rate_pct: 0.0, average_convenience_fee: 0.0, average_markup_over_direct: 552.44 },
                      { source_name: "Cleartrip", domain: "cleartrip.com", quotes_count: 5, cheapest_win_rate_pct: 0.0, average_convenience_fee: 349.0, average_markup_over_direct: 701.44 },
                      { source_name: "Ixigo Flights", domain: "ixigo.com", quotes_count: 5, cheapest_win_rate_pct: 0.0, average_convenience_fee: 360.0, average_markup_over_direct: 742.44 },
                      { source_name: "MakeMyTrip India", domain: "makemytrip.com", quotes_count: 5, cheapest_win_rate_pct: 0.0, average_convenience_fee: 420.0, average_markup_over_direct: 772.44 },
                      { source_name: "Yatra Online", domain: "yatra.com", quotes_count: 5, cheapest_win_rate_pct: 0.0, average_convenience_fee: 399.0, average_markup_over_direct: 801.44 },
                    ]).map((plat, idx) => {
                      const isCarrier = plat.source_name.startsWith("Carrier Direct");
                      const isZeroFee = plat.average_convenience_fee === 0;

                      return (
                        <tr key={idx} className="hover:bg-canvas/60 transition-colors">
                          <td className="py-3 pr-4">
                            <div className="font-semibold text-ink font-sans flex items-center gap-1.5">
                              {isCarrier ? (
                                <Building2 className="h-3.5 w-3.5 text-mid-gray" />
                              ) : (
                                <Globe className="h-3.5 w-3.5 text-mid-gray" />
                              )}
                              <span>{plat.source_name}</span>
                            </div>
                            <span className="text-[10px] text-mid-gray font-mono">{plat.domain}</span>
                          </td>
                          <td className="py-3 font-mono text-[11px]">
                            <span className={`px-2 py-0.5 rounded-[12px] text-[10px] ${
                              isCarrier 
                                ? "bg-canvas text-ink border border-hairline font-medium" 
                                : plat.domain.includes("skyscanner")
                                ? "bg-canvas text-mid-gray border border-hairline"
                                : "bg-canvas text-mid-gray border border-hairline"
                            }`}>
                              {isCarrier ? "CARRIER DIRECT" : plat.domain.includes("skyscanner") ? "METASEARCH" : "ONLINE AGGREGATOR"}
                            </span>
                          </td>
                          <td className="py-3 font-mono text-xs">
                            {isZeroFee ? (
                              <span className="inline-flex items-center gap-1 font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                                ₹0 (Zero Fee)
                              </span>
                            ) : (
                              <span className="text-ink-soft">
                                ₹{plat.average_convenience_fee}
                              </span>
                            )}
                          </td>
                          <td className="py-3 font-mono text-[11px] text-mid-gray">
                            <span className="text-ink font-medium">Standard Retail</span>
                            <div className="text-[10px] text-mid-gray">Bank promo isolated</div>
                          </td>
                          <td className="py-3 font-mono text-xs">
                            {plat.cheapest_win_rate_pct > 0 ? (
                              <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                                {plat.cheapest_win_rate_pct.toFixed(1)}%
                              </span>
                            ) : (
                              <span className="text-mid-gray">0.0%</span>
                            )}
                          </td>
                          <td className="py-3 font-mono text-xs">
                            {isCarrier ? (
                              <span className="text-mid-gray font-mono">0.0% (Base)</span>
                            ) : (
                              <span className="text-ink font-medium">
                                +₹{Math.round(plat.average_markup_over_direct)} ({((plat.average_markup_over_direct / 3500) * 100).toFixed(1)}%)
                              </span>
                            )}
                          </td>
                          <td className="py-3">
                            <Badge variant="safe" size="xs">
                              Healthy
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Institutional Methodology Framework */}
          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-ink" />
              <h4 className="font-semibold text-xs text-ink font-sans uppercase tracking-wider">
                MoSPI / NSO Cross-Platform Price Harmonization Methodology
              </h4>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-sans">
              <div className="rounded-nested border border-hairline bg-canvas p-4 space-y-2">
                <span className="font-semibold text-ink flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-ink" />
                  1. Harmonized Median Fare
                </span>
                <p className="text-mid-gray leading-relaxed text-[11px]">
                  When identical flights (e.g. 6E-205) are quoted across multiple OTAs with differing markups, the <strong className="text-ink">Harmonized Platform Median</strong> is computed. It is mathematically robust against single-platform markup spikes, flash gouging, or phantom seat inventory.
                </p>
              </div>

              <div className="rounded-nested border border-hairline bg-canvas p-4 space-y-2">
                <span className="font-semibold text-ink flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-ink" />
                  2. Convenience Fee Unbundling
                </span>
                <p className="text-mid-gray leading-relaxed text-[11px]">
                  Under Indian consumer protection guidelines and Section 62 data validation, mandatory booking/convenience fees (ranging from ₹0 on EaseMyTrip to ₹420 on MakeMyTrip) are explicitly tracked and unbundled to reflect genuine consumer walkaway expenditure.
                </p>
              </div>

              <div className="rounded-nested border border-hairline bg-canvas p-4 space-y-2">
                <span className="font-semibold text-ink flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-ink" />
                  3. Payment Instrument Isolation
                </span>
                <p className="text-mid-gray leading-relaxed text-[11px]">
                  Promotional bank discounts (e.g. 10% instant off on specific bank credit cards) are conditional and excluded from baseline CPI collection to preserve standard Laspeyres index comparability across homogeneous expenditure brackets.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function MarketDynamicsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-xs font-mono text-mid-gray">Loading Market Dynamics Workbench...</div>}>
      <MarketDynamicsContent />
    </Suspense>
  );
}
