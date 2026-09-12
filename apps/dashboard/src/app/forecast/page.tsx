"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ForecastChart, ForecastChartDataPoint } from "@/components/charts/ForecastChart";
import { StatCard } from "@/components/ui/StatCard";
import { Button } from "@/components/ui/Button";
import { fetchFromApi, HistoryAndForecastResponse, ForecastAccuracyResponse } from "@/lib/api";
import {
  Sparkles,
  ChevronRight,
  TrendingUp,
  Download,
  RefreshCw,
  Calendar,
  Clock,
  BarChart3,
  LineChart,
  Filter,
  Search,
  Zap,
  Shield,
  Flame,
} from "lucide-react";

export default function ForecastPage() {
  const [priceSeries, setPriceSeries] = useState<"BASE_FARE" | "TOTAL_PRICE">("BASE_FARE");
  const [selectedIndexType, setSelectedIndexType] = useState<"HEADLINE_T15" | "SUB_T1" | "SUB_T7" | "SUB_T30" | "SUB_T45">("HEADLINE_T15");
  const [horizon, setHorizon] = useState(28);
  const [historyDays, setHistoryDays] = useState(28);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"detail" | "all">("detail");

  const [historyForecast, setHistoryForecast] = useState<HistoryAndForecastResponse | null>(null);
  const [accuracy, setAccuracy] = useState<ForecastAccuracyResponse | null>(null);

  const loadForecast = async () => {
    setLoading(true);
    try {
      const [data, acc] = await Promise.all([
        fetchFromApi<HistoryAndForecastResponse>(
          `/forecast/history-and-forecast?series=${priceSeries}&index_type=${selectedIndexType}&history_days=${historyDays}&horizon=${horizon}`
        ),
        fetchFromApi<ForecastAccuracyResponse>(
          `/forecast/accuracy?series=${priceSeries}&index_type=${selectedIndexType}&lookback_days=180`
        ),
      ]);
      setHistoryForecast(data);
      setAccuracy(acc);
    } catch (err) {
      console.error("Failed to load forecast:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadForecast();
  }, [priceSeries, selectedIndexType, horizon, historyDays]);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="card-panel p-6 h-64 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card-panel p-4 h-32 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const currentVal = historyForecast?.history?.[historyForecast.history.length - 1]?.value ?? 100;
  const vsBasePct = (currentVal - 100).toFixed(2);
  const yKey = priceSeries === "BASE_FARE" ? "baseVal" : "totalVal";

  const leadTimeRibbon = [
    { horizon: "T+1", title: "Departure Eve", val: "—", change: "—", status: "Severe Yield Surge", badgeVariant: "danger" as const },
    { horizon: "T+7", title: "1 Week Out", val: "—", change: "—", status: "Elevated Yields", badgeVariant: "warning" as const },
    { horizon: "T+15", title: "Anchor (2 Weeks)", val: currentVal.toFixed(2), change: "+" + vsBasePct + "%", status: "Headline Anchor", badgeVariant: "solid" as const },
    { horizon: "T+30", title: "1 Month Out", val: "—", change: "—", status: "Consumer Baseline", badgeVariant: "info" as const },
    { horizon: "T+45", title: "Early Bird", val: "—", change: "—", status: "Safe Discount Tier", badgeVariant: "success" as const },
  ];

  function Header() {
    return (
      <SectionHeader
        title="Probabilistic Forecast Engine"
        headline="28-day ensemble forecasts combining TimesFM 2.5, LightGBM, and Statistical models with conformal prediction intervals."
        badge="ENSEMBLE: TimesFM 50% · LightGBM 35% · Statistical 15%"
        badgeVariant="solid"
        action={
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-2 border border-border rounded-xl bg-card/50 px-3 py-2">
              <Calendar className="h-4 w-4 text-muted-foreground mr-2" />
              <select
                value={historyDays}
                onChange={(e) => setHistoryDays(Number(e.target.value))}
                className="bg-transparent text-foreground text-sm font-medium focus:outline-none"
              >
                <option value={14}>14d History</option>
                <option value={28}>28d History</option>
                <option value={60}>60d History</option>
              </select>
            </div>
            <div className="flex items-center gap-2 border border-border rounded-xl bg-card/50 px-3 py-2">
              <Clock className="h-4 w-4 text-muted-foreground mr-2" />
              <select
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="bg-transparent text-foreground text-sm font-medium focus:outline-none"
              >
                <option value={7}>7 Days</option>
                <option value={14}>14 Days</option>
                <option value={28}>28 Days</option>
              </select>
            </div>
            <Button variant="outline" size="sm" onClick={loadForecast} disabled={loading}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
            <Button size="sm" onClick={() => { /* TODO: export */ }}>
              <Download className="h-4 w-4 mr-2" />
              Export CSV
            </Button>
          </div>
        }
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <Header />

      {/* Headline KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Headline Index (T+15)"
          value={historyForecast?.history?.[historyForecast.history.length - 1]?.value?.toFixed(2) ?? "—"}
          subtitle={`Base 2026-08-01 = 100 | ${historyForecast?.history?.[historyForecast.history.length - 1]?.date ?? "—"}`}
          icon={<TrendingUp className="h-6 w-6" />}
          trend={{ value: "—", direction: "neutral" as const, label: "24h" }}
          badge="LIVE"
          badgeVariant="success"
        />
        <StatCard
          title="Weekly Change"
          value="—"
          subtitle="7-day momentum"
          icon={<Zap className="h-6 w-6" />}
          badge="HIGH COV"
          badgeVariant="success"
        />
        <StatCard
          title="Monthly Change"
          value="—"
          subtitle="30-day trajectory"
          icon={<BarChart3 className="h-6 w-6" />}
        />
        <StatCard
          title="Coverage"
          value={`${historyForecast?.history.length ?? 0} days`}
          subtitle={`${historyForecast?.index_type?.replace("HEADLINE_", "T") ?? "T+15"} Anchor`}
          icon={<Shield className="h-6 w-6" />}
          badge="FULL"
          badgeVariant="success"
        />
        <StatCard
          title="Quality Score"
          value="—"
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

        {historyForecast && historyForecast.history.length > 0 && historyForecast.forecast.length > 0 && (
          <>
            <ForecastChart
              data={[
                ...historyForecast.history.map<ForecastChartDataPoint>(h => ({
                  date: h.date.slice(5),
                  baseVal: h.value ?? 0,
                  isForecast: false,
                  p10: undefined,
                  p25: undefined,
                  p50: undefined,
                  p75: undefined,
                  p90: undefined,
                  modelConfidence: undefined,
                })),
                ...historyForecast.forecast.map<ForecastChartDataPoint>(f => ({
                  date: f.date.slice(5),
                  baseVal: f.p50 ?? 0,
                  isForecast: true,
                  p10: f.p10,
                  p25: f.p25,
                  p50: f.p50,
                  p75: f.p75,
                  p90: f.p90,
                  modelConfidence: f.model_confidence,
                })),
              ]}
              xKey="date"
              yKey="baseVal"
              height={400}
              color="orange"
              showForecastBands={true}
              showConfidence={true}
              valuePrefix="Index: "
            />

            {/* Forecast Table */}
            <div className="card-panel p-6">
              <h3 className="text-lg font-bold mb-4">Forecast Details (P10/P25/P50/P75/P90)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground font-mono uppercase tracking-wider text-[10px]">
                      <th className="pb-3 text-left">Date</th>
                      <th className="pb-3 text-left">Horizon</th>
                      <th className="pb-3 text-left">P10</th>
                      <th className="pb-3 text-left">P25</th>
                      <th className="pb-3 text-left">P50 (Median)</th>
                      <th className="pb-3 text-left">P75</th>
                      <th className="pb-3 text-left">P90</th>
                      <th className="pb-3 text-left">Confidence</th>
                      <th className="pb-3 text-left">Components</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {historyForecast.forecast.map((point) => (
                      <tr key={point.date} className="hover:bg-accent/50">
                        <td className="py-3 font-mono">{point.date}</td>
                        <td className="py-3 font-mono">{horizon}d</td>
                        <td className="py-3 font-mono text-red-400">{point.p10?.toFixed(2) ?? "—"}</td>
                        <td className="py-3 font-mono text-amber-400">{point.p25?.toFixed(2) ?? "—"}</td>
                        <td className="py-3 font-mono font-bold text-foreground">{point.p50?.toFixed(2) ?? "—"}</td>
                        <td className="py-3 font-mono text-amber-400">{point.p75?.toFixed(2) ?? "—"}</td>
                        <td className="py-3 font-mono text-red-400">{point.p90?.toFixed(2) ?? "—"}</td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-4 w-16 bg-border rounded-full overflow-hidden">
                              <div className="h-full bg-orange-500 rounded-full" style={{ width: `${((point.model_confidence ?? 0) * 100)}%` }} />
                            </div>
                            <span className="text-xs font-mono text-muted-foreground">{((point.model_confidence ?? 0) * 100).toFixed(0)}%</span>
                          </div>
                        </td>
                        <td className="py-3 text-xs text-muted-foreground max-w-xs truncate">
                          —
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Methodology Card */}
            <div className="card-panel p-6 border-orange-500/20 bg-gradient-to-r from-orange-500/5 via-amber-500/2 to-transparent">
              <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-orange-400" />
                Forecast Methodology
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="p-4 rounded-xl bg-card/50 border border-border">
                  <h4 className="font-semibold text-orange-400 mb-2 flex items-center gap-2">
                    <Sparkles className="h-4 w-4" /> TimesFM 2.5 (50%)
                  </h4>
                  <p className="text-muted-foreground">Google&apos;s 200M-parameter time-series foundation model. Zero-shot forecasting with quantile outputs. Context length 512, horizon 28.</p>
                </div>
                <div className="p-4 rounded-xl bg-card/50 border border-border">
                  <h4 className="font-semibold text-emerald-400 mb-2 flex items-center gap-2">
                    <Zap className="h-4 w-4" /> LightGBM + Conformal (35%)
                  </h4>
                  <p className="text-muted-foreground">Gradient boosted trees with 500+ features (lags, rolling stats, calendar, fuel, FX). Conformal prediction for valid P10/P90 intervals.</p>
                </div>
                <div className="p-4 rounded-xl bg-card/50 border border-border">
                  <h4 className="font-semibold text-cyan-400 mb-2 flex items-center gap-2">
                    <LineChart className="h-4 w-4" /> Statistical STL+ARIMA (15%)
                  </h4>
                  <p className="text-muted-foreground">Seasonal-trend decomposition (STL) + ARIMA on residuals. Robust baseline when ML models disagree.</p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Forecast Backtest Accuracy */}
      <div className="card-panel p-6 space-y-4 border-emerald-500/20">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-emerald-400" />
              Forecast Backtest Accuracy
            </h3>
            <p className="text-sm text-muted-foreground mt-1">Stored forecast snapshots scored against realized index values (MAE/RMSE/MAPE, P50 hit rate, interval coverage)</p>
          </div>
          <Badge variant="outline" size="sm" className="font-mono">
            {accuracy?.lookback_days ?? 180}d lookback
          </Badge>
        </div>

        {accuracy && accuracy.results.length > 0 ? (
          accuracy.results.map((item) => (
            <div key={`${item.series}-${item.index_type}`} className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="rounded-xl bg-card/50 border border-border p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">MAE</div>
                  <div className="text-xl font-bold font-mono">{item.mae.toFixed(2)}</div>
                </div>
                <div className="rounded-xl bg-card/50 border border-border p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">RMSE</div>
                  <div className="text-xl font-bold font-mono">{item.rmse.toFixed(2)}</div>
                </div>
                <div className="rounded-xl bg-card/50 border border-border p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">MAPE</div>
                  <div className="text-xl font-bold font-mono">{item.mape_pct.toFixed(2)}%</div>
                </div>
                <div className="rounded-xl bg-card/50 border border-border p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Bias</div>
                  <div className={`text-xl font-bold font-mono ${item.bias > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                    {item.bias > 0 ? "+" : ""}{item.bias.toFixed(2)}
                  </div>
                </div>
                <div className="rounded-xl bg-card/50 border border-border p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">P50 Hit</div>
                  <div className="text-xl font-bold font-mono">{item.p50_hit_rate_pct.toFixed(0)}%</div>
                </div>
                <div className="rounded-xl bg-card/50 border border-border p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">P10-P90 Cov</div>
                  <div className="text-xl font-bold font-mono">{item.p10_p90_coverage_pct.toFixed(0)}%</div>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card/30 overflow-hidden">
                <div className="px-4 py-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center justify-between bg-border/20">
                  <span>Dated Forecasts: {item.matched_count} matched / {item.snapshot_count} stored</span>
                  <span>{item.series} · {item.index_type}</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground font-mono uppercase tracking-wider text-[10px]">
                        <th className="px-4 py-2 text-left">Target Date</th>
                        <th className="px-4 py-2 text-left">Horizon</th>
                        <th className="px-4 py-2 text-left">Actual</th>
                        <th className="px-4 py-2 text-left">P10</th>
                        <th className="px-4 py-2 text-left">P50</th>
                        <th className="px-4 py-2 text-left">P90</th>
                        <th className="px-4 py-2 text-left">Error</th>
                        <th className="px-4 py-2 text-left">Covered</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {item.recent.slice(0, 10).map((r) => {
                        const error = r.actual - (r.p50 ?? 0);
                        const covered = r.p10 !== null && r.p90 !== null && r.actual >= r.p10 && r.actual <= r.p90;
                        return (
                          <tr key={r.target_date} className="hover:bg-accent/50">
                            <td className="px-4 py-2 font-mono">{r.target_date}</td>
                            <td className="px-4 py-2 font-mono">{r.horizon_days}d</td>
                            <td className="px-4 py-2 font-mono">{r.actual.toFixed(2)}</td>
                            <td className="px-4 py-2 font-mono text-red-400">{r.p10?.toFixed(2) ?? "—"}</td>
                            <td className="px-4 py-2 font-mono font-bold text-foreground">{r.p50?.toFixed(2) ?? "—"}</td>
                            <td className="px-4 py-2 font-mono text-red-400">{r.p90?.toFixed(2) ?? "—"}</td>
                            <td className="px-4 py-2 font-mono text-amber-400">{error > 0 ? "+" : ""}{error.toFixed(2)}</td>
                            <td className="px-4 py-2">
                              {covered ? (
                                <Badge variant="success" size="sm">IN</Badge>
                              ) : (
                                <Badge variant="warning" size="sm">OUT</Badge>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-card/20 p-8 text-center">
            <p className="text-sm text-muted-foreground">
              No matured forecasts yet. As forecasts are generated and their target dates pass, the system
              automatically scores them here against realized index values.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}