"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ForecastChart } from "@/components/charts/ForecastChart";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { 
  TrendingUp, 
  ArrowRight, 
  Shield, 
  Layers, 
  Plane, 
  Calendar,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Zap,
  BarChart3,
  Flame,
  Search,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { fetchFromApi, IndexResponse, CorridorItem, DataQualityResponse, MarketBriefingData, HistoryAndForecastResponse } from "@/lib/api";

export default function NationalOverviewPage() {
  const [priceSeries, setPriceSeries] = useState<"BASE_FARE" | "TOTAL_PRICE">("BASE_FARE");
  const [loading, setLoading] = useState(true);

  const [headline, setHeadline] = useState<IndexResponse | null>(null);
  const [trendData, setTrendData] = useState<Array<{ date: string; baseVal: number; totalVal: number; isForecast?: boolean; p10?: number; p25?: number; p50?: number; p75?: number; p90?: number; modelConfidence?: number }>>([]);
  const [ribbonMap, setRibbonMap] = useState<Record<string, { val: string; change: string }>>({});
  const [corridors, setCorridors] = useState<CorridorItem[]>([]);
  const [quality, setQuality] = useState<DataQualityResponse | null>(null);
  const [marketBriefing, setMarketBriefing] = useState<MarketBriefingData | null>(null);
  const [historyForecast, setHistoryForecast] = useState<HistoryAndForecastResponse | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadLiveObservatoryData() {
      try {
        setLoading(true);
        
        const hData = await fetchFromApi<IndexResponse>(
          `/index?series=${priceSeries}&horizon=t15`
        );

        const hfData = await fetchFromApi<HistoryAndForecastResponse>(
          `/forecast/history-and-forecast?series=${priceSeries}&index_type=HEADLINE_T15&history_days=28&horizon=28`
        );

        const [t1, t7, t15, t30, t45] = await Promise.all([
          fetchFromApi<IndexResponse>(`/index?series=${priceSeries}&horizon=t1`),
          fetchFromApi<IndexResponse>(`/index?series=${priceSeries}&horizon=t7`),
          fetchFromApi<IndexResponse>(`/index?series=${priceSeries}&horizon=t15`),
          fetchFromApi<IndexResponse>(`/index?series=${priceSeries}&horizon=t30`),
          fetchFromApi<IndexResponse>(`/index?series=${priceSeries}&horizon=t45`),
        ]);

        const cData = await fetchFromApi<CorridorItem[]>("/routes");
        const qData = await fetchFromApi<DataQualityResponse>("/data-quality");
        const mbData = await fetchFromApi<MarketBriefingData>(
          `/analytics/market-briefing?series=${priceSeries}&horizon=15`
        );

        if (isMounted) {
          setHeadline(hData);
          
          if (hfData && hfData.history) {
            const combined = [
              ...hfData.history.map((h) => ({
                date: h.date.slice(5),
                baseVal: priceSeries === "BASE_FARE" ? (h.value ?? 0) : (h.value ?? 0) * 0.985,
                totalVal: priceSeries === "TOTAL_PRICE" ? (h.value ?? 0) : (h.value ?? 0) * 1.015,
                isForecast: h.type === "forecast",
                p10: h.p10,
                p25: h.p25,
                p50: h.p50,
                p75: h.p75,
                p90: h.p90,
                modelConfidence: h.model_confidence,
              })),
              ...hfData.forecast.map((f) => ({
                date: f.date.slice(5),
                baseVal: priceSeries === "BASE_FARE" ? (f.p50 ?? 0) : (f.p50 ?? 0) * 0.985,
                totalVal: priceSeries === "TOTAL_PRICE" ? (f.p50 ?? 0) : (f.p50 ?? 0) * 1.015,
                isForecast: true,
                p10: f.p10,
                p25: f.p25,
                p50: f.p50,
                p75: f.p75,
                p90: f.p90,
                modelConfidence: f.model_confidence,
              })),
            ];
            setTrendData(combined);
          }
          setHistoryForecast(hfData);
          
          setRibbonMap({
            "T+1": { val: t1?.index_value?.toFixed(2) ?? "—", change: t1?.index_value != null ? `+${((t1.index_value - 100)).toFixed(1)}%` : "—" },
            "T+7": { val: t7?.index_value?.toFixed(2) ?? "—", change: t7?.index_value != null ? `+${((t7.index_value - 100)).toFixed(1)}%` : "—" },
            "T+15": { val: t15?.index_value?.toFixed(2) ?? "—", change: t15?.index_value != null ? `+${((t15.index_value - 100)).toFixed(1)}%` : "—" },
            "T+30": { val: t30?.index_value?.toFixed(2) ?? "—", change: t30?.index_value != null ? `${((t30.index_value - 100)).toFixed(1)}%` : "—" },
            "T+45": { val: t45?.index_value?.toFixed(2) ?? "—", change: t45?.index_value != null ? `${((t45.index_value - 100)).toFixed(1)}%` : "—" },
          });
          setCorridors(cData || []);
          setQuality(qData);
          setMarketBriefing(mbData);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load observatory data:", err);
        if (isMounted) setLoading(false);
      }
    }

    loadLiveObservatoryData();
    return () => { isMounted = false; };
  }, [priceSeries]);

  if (loading) {
    return (
      <div className="space-y-8 animate-pulse">
        <SectionHeader title="Loading Phoenix Observatory..." headline="Initializing real-time data feeds..." />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card-panel p-6 h-32 animate-pulse" />
          ))}
        </div>
        <div className="card-panel p-6 h-64 animate-pulse" />
      </div>
    );
  }

  const currentVal = headline?.index_value ?? 100;
  const currentDelta = headline?.daily_change_pct ?? 0;
  const vsBasePct = (currentVal - 100).toFixed(2);
  const yKey = priceSeries === "BASE_FARE" ? "baseVal" : "totalVal";

  const leadTimeRibbon = [
    { horizon: "T+1", title: "Departure Eve", val: ribbonMap["T+1"]?.val || "—", change: ribbonMap["T+1"]?.change || "—", status: "Severe Yield Surge", badgeVariant: "danger" as const },
    { horizon: "T+7", title: "1 Week Out", val: ribbonMap["T+7"]?.val || "—", change: ribbonMap["T+7"]?.change || "—", status: "Elevated Yields", badgeVariant: "warning" as const },
    { horizon: "T+15", title: "Anchor (2 Weeks)", val: currentVal.toFixed(2), change: `+${vsBasePct}%`, status: "Headline Anchor", badgeVariant: "solid" as const },
    { horizon: "T+30", title: "1 Month Out", val: ribbonMap["T+30"]?.val || "—", change: ribbonMap["T+30"]?.change || "—", status: "Consumer Baseline", badgeVariant: "info" as const },
    { horizon: "T+45", title: "Early Bird", val: ribbonMap["T+45"]?.val || "—", change: ribbonMap["T+45"]?.change || "—", status: "Safe Discount Tier", badgeVariant: "success" as const },
  ];

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <SectionHeader
        title="Phoenix National Airfare Observatory"
        headline="High-frequency algorithmic price index tracking retail domestic airfare inflation across India's primary aviation corridors."
        badge="PHOENIX QUANT ENGINE · LIVE"
        badgeVariant="solid"
        action={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setPriceSeries("BASE_FARE")} className={priceSeries === "BASE_FARE" ? "bg-orange-500/20 border-orange-500/30 text-orange-400" : ""}>
              Base Fare
            </Button>
            <Button variant="outline" size="sm" onClick={() => setPriceSeries("TOTAL_PRICE")} className={priceSeries === "TOTAL_PRICE" ? "bg-orange-500/20 border-orange-500/30 text-orange-400" : ""}>
              Total Price
            </Button>
            <Button size="sm" onClick={() => window.location.reload()}>
              <Sparkles className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        }
      />

      {/* Headline KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Headline Index (T+15)"
          value={headline?.index_value?.toFixed(2) ?? "—"}
          subtitle={`Base 2026-08-01 = 100 | ${headline?.period_start ?? "—"}`}
          icon={<TrendingUp className="h-6 w-6" />}
          trend={{ value: `${headline?.daily_change_pct ?? 0 >= 0 ? "+" : ""}${headline?.daily_change_pct?.toFixed(2) ?? "0.00"}%`, direction: (headline?.daily_change_pct ?? 0) >= 0 ? "up" : "down", label: "24h" }}
          badge="LIVE"
          badgeVariant="success"
        />
        <StatCard
          title="Weekly Change"
          value={`${headline?.weekly_change_pct ?? 0 >= 0 ? "+" : ""}${headline?.weekly_change_pct?.toFixed(2) ?? "0.00"}%`}
          subtitle="7-day momentum"
          icon={<Zap className="h-6 w-6" />}
          badge={headline?.is_low_coverage ? "LOW COV" : "HIGH COV"}
          badgeVariant={headline?.is_low_coverage ? "danger" : "success"}
        />
        <StatCard
          title="Monthly Change"
          value={`${headline?.monthly_change_pct ?? 0 >= 0 ? "+" : ""}${headline?.monthly_change_pct?.toFixed(2) ?? "0.00"}%`}
          subtitle="30-day trajectory"
          icon={<BarChart3 className="h-6 w-6" />}
        />
        <StatCard
          title="Coverage"
          value={`${headline?.coverage_rate?.toFixed(1) ?? "100"}%`}
          subtitle={`${headline?.index_type?.replace("HEADLINE_", "T") ?? "T+15"} Anchor`}
          icon={<Shield className="h-6 w-6" />}
          badge={headline?.is_low_coverage ? "LOW" : "FULL"}
          badgeVariant={headline?.is_low_coverage ? "warning" : "success"}
        />
        <StatCard
          title="Quality Score"
          value={quality ? `${Math.round(quality.quote_capture_rate_pct)}%` : "—"}
          subtitle="Composite (coverage, feed, diversity)"
          icon={<Shield className="h-6 w-6" />}
          badge="LIVE"
          badgeVariant="success"
        />
      </div>

      {/* Lead-Time Ribbon */}
      <div className="card-panel p-6 space-y-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-orange-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-foreground font-mono flex items-center gap-2">
              Lead-Time Price Elasticity Ribbon
              <span className="h-1.5 w-1.5 rounded-full bg-orange-400" />
            </h3>
          </div>
          <Badge variant="outline" className="text-[11px] font-mono">
            Unpooled Horizons · DGCA Weighted
          </Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {leadTimeRibbon.map((item) => (
            <Link
              key={item.horizon}
              href={`/lead-time?horizon=${item.horizon}`}
              className={`group relative rounded-xl border p-4 transition-all ${
                item.badgeVariant === "solid"
                  ? "bg-gradient-to-r from-orange-500/20 to-amber-500/20 border-orange-500/30 shadow-sm shadow-orange-500/10"
                  : item.badgeVariant === "danger"
                  ? "border-red-500/30 bg-red-500/5"
                  : item.badgeVariant === "warning"
                  ? "border-amber-500/30 bg-amber-500/5"
                  : item.badgeVariant === "success"
                  ? "border-emerald-500/30 bg-emerald-500/5"
                  : item.badgeVariant === "info"
                  ? "border-cyan-500/30 bg-cyan-500/5"
                  : "border-slate-500/30 bg-slate-500/5"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <Badge variant={item.badgeVariant === "solid" ? "default" : item.badgeVariant} size="sm">
                  {item.horizon}
                </Badge>
                <span className="text-[10px] font-mono text-muted-foreground">{item.title}</span>
              </div>
              <div className="text-2xl font-bold font-mono text-foreground group-hover:text-orange-400 transition-colors">
                {item.val}
              </div>
              <div className="flex items-center gap-1.5 mt-1">
                <span className="text-xs font-semibold font-mono text-orange-400">{item.change}</span>
                <span className="text-[10px] text-muted-foreground">{item.status}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Main Chart: History + Forecast */}
      <div className="card-panel p-6 space-y-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Calendar className="h-5 w-5 text-orange-400" />
              56-Day Timeline: Past 28 Days + Future 28 Days
            </h3>
            <p className="text-sm text-muted-foreground mt-1">Ensemble forecast: TimesFM 2.5 (50%) + LightGBM (35%) + Statistical (15%) · P10-P90 bands</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" size="sm">TimesFM 50%</Badge>
            <Badge variant="outline" size="sm">LightGBM 35%</Badge>
            <Badge variant="outline" size="sm">Statistical 15%</Badge>
          </div>
        </div>

        <ForecastChart
          data={trendData}
          xKey="date"
          yKey={yKey}
          height={320}
          color="orange"
          showForecastBands={true}
          showConfidence={true}
          valuePrefix="Index: "
        />
      </div>

      {/* Corridor Quick View */}
      <div className="card-panel p-6 space-y-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
              <Plane className="h-5 w-5 text-orange-400" />
              Corridor Matrix — Real-Time Representative Prices
            </h3>
            <p className="text-sm text-muted-foreground">10 DGCA corridors · Median carrier fare · Click for fare anatomy</p>
          </div>
          <Link href="/corridors" className="text-sm font-semibold text-orange-400 hover:text-orange-300 flex items-center gap-1">
            View All Corridors <ChevronRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground font-mono uppercase tracking-wider text-[10px]">
                <th className="pb-3 text-left">Route</th>
                <th className="pb-3 text-left">Type</th>
                <th className="pb-3 text-left">Weight</th>
                <th className="pb-3 text-left">Rep. Price</th>
                <th className="pb-3 text-left">Index (T+15)</th>
                <th className="pb-3 text-left">7D Δ</th>
                <th className="pb-3 text-left">Monthly Δ</th>
                <th className="pb-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {corridors.slice(0, 6).map((row) => (
                <tr key={row.route_code} className="hover:bg-accent/50 transition-colors">
                  <td className="py-3">
                    <div className="font-mono font-bold text-foreground">{row.route_code}</div>
                    <div className="text-xs text-muted-foreground">{row.origin} ↔ {row.destination}</div>
                  </td>
                  <td className="py-3">
                    <Badge variant={row.corridor_type === "METRO_TRUNK" ? "neutral" : "warning"} size="sm">
                      {row.corridor_type === "METRO_TRUNK" ? "METRO" : "REGIONAL"}
                    </Badge>
                  </td>
                  <td className="py-3 font-mono text-sm text-muted-foreground">
                    {(row.dgca_weight * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 font-mono font-semibold text-foreground">
                    {row.representative_price ? `₹${row.representative_price.toLocaleString("en-IN")}` : "—"}
                  </td>
                  <td className="py-3 font-mono font-bold text-cyan-400">
                    {row.current_index?.toFixed(2) ?? "—"}
                  </td>
                  <td className="py-3">
                    <Badge variant={row.daily_change_pct && row.daily_change_pct > 0 ? "danger" : row.daily_change_pct && row.daily_change_pct < 0 ? "success" : "neutral"} size="sm">
                      {row.daily_change_pct != null ? `${row.daily_change_pct >= 0 ? "+" : ""}${row.daily_change_pct.toFixed(1)}%` : "—"}
                    </Badge>
                  </td>
                  <td className="py-3">
                    <Badge variant={row.monthly_change_pct && row.monthly_change_pct > 0 ? "danger" : row.monthly_change_pct && row.monthly_change_pct < 0 ? "success" : "neutral"} size="sm">
                      {row.monthly_change_pct != null ? `${row.monthly_change_pct >= 0 ? "+" : ""}${row.monthly_change_pct.toFixed(1)}%` : "—"}
                    </Badge>
                  </td>
                  <td className="py-3 text-right">
                    <Link href={`/corridors/${row.route_code}`} className="text-xs font-semibold text-orange-400 hover:text-orange-300 flex items-center gap-1 group">
                      <span>Inspect</span>
                      <ChevronRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Market Briefing */}
      {marketBriefing && (
        <div className="card-panel p-6 space-y-4">
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-orange-400" />
            Executive Market Briefing
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Inflation Leader</p>
              <p className="text-xl font-bold">{marketBriefing.carrier_power?.inflation_leader ?? "—"}</p>
              <p className="text-sm text-muted-foreground">{marketBriefing.carrier_power?.inflation_leader_code ?? ""} · Index: {marketBriefing.carrier_power?.inflation_leader_index?.toFixed(1) ?? "—"}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Value Leader</p>
              <p className="text-xl font-bold">{marketBriefing.carrier_power?.value_leader ?? "—"}</p>
              <p className="text-sm text-muted-foreground">{marketBriefing.carrier_power?.value_leader_code ?? ""} · Min Fare: ₹{marketBriefing.carrier_power?.value_leader_min_fare?.toLocaleString() ?? "—"}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Network Volatility</p>
              <p className="text-xl font-bold">{marketBriefing.volatility?.average_network_spread_pct?.toFixed(1) ?? "—"}%</p>
              <p className="text-sm text-muted-foreground">{marketBriefing.volatility?.active_surge_corridors_count ?? 0} surge corridors</p>
            </Card>
          </div>
        </div>
      )}

      {/* Data Quality Footer */}
      {quality && (
        <div className="card-panel p-6">
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2 mb-4">
            <Shield className="h-5 w-5 text-emerald-400" />
            Data Quality & Pipeline Health
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="p-4 rounded-xl bg-card border border-border">
              <p className="text-3xl font-bold text-emerald-400">{quality.quote_capture_rate_pct?.toFixed(1) ?? "—"}%</p>
              <p className="text-xs text-muted-foreground mt-1">Quote Capture Rate</p>
            </div>
            <div className="p-4 rounded-xl bg-card border border-border">
              <p className="text-3xl font-bold text-cyan-400">{quality.real_life_share_pct?.toFixed(1) ?? "100"}%</p>
              <p className="text-xs text-muted-foreground mt-1">Real-World Authentic</p>
            </div>
            <div className="p-4 rounded-xl bg-card border border-border">
              <p className="text-3xl font-bold text-orange-400">{quality.valid_quotes_count ?? "—"}</p>
              <p className="text-xs text-muted-foreground mt-1">Valid Quotes</p>
            </div>
            <div className="p-4 rounded-xl bg-card border border-border">
              <p className="text-3xl font-bold text-amber-400">{quality.rejected_quotes_count ?? "—"}</p>
              <p className="text-xs text-muted-foreground mt-1">Rejected</p>
            </div>
          </div>
        </div>
      )}

      {/* Footer CTA */}
      <div className="card-panel p-8 text-center bg-gradient-to-r from-orange-500/10 via-amber-500/5 to-transparent border-orange-500/20">
        <h3 className="text-xl font-bold mb-2">Ready to Integrate?</h3>
        <p className="text-muted-foreground mb-6 max-w-2xl mx-auto">
          Access real-time index data, forecasts, and corridor intelligence via our REST API. 
          Built for airlines, airports, OTAs, and policymakers.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Link href="/api/docs" className="btn-primary">
            <ExternalLink className="h-4 w-4 mr-2" />
            API Documentation
          </Link>
          <Link href="/forecast" className="btn-secondary">
            <Sparkles className="h-4 w-4 mr-2" />
            View Forecasts
          </Link>
        </div>
      </div>
    </div>
  );
}