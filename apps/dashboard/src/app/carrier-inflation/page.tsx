"use client";

import React, { useState, useEffect } from "react";
import { 
  fetchFromApi, 
  CarrierInflationResponse, 
  CarrierTimeseriesPoint, 
  CorridorItem 
} from "@/lib/api";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { LineChart, SeriesConfig } from "@/components/charts/LineChart";
import { 
  TrendingUp, 
  Plane, 
  Layers, 
  AlertCircle, 
  Scale, 
  Info,
  Calendar,
  CheckCircle2
} from "lucide-react";

export default function CarrierInflationPage() {
  const [horizon, setHorizon] = useState<number>(15);
  const [inflationData, setInflationData] = useState<CarrierInflationResponse | null>(null);
  const [timeseries, setTimeseries] = useState<CarrierTimeseriesPoint[]>([]);
  const [corridors, setCorridors] = useState<CorridorItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const [inf, ts, rts] = await Promise.all([
        fetchFromApi<CarrierInflationResponse>(`/analytics/carrier-inflation?horizon=${horizon}`),
        fetchFromApi<CarrierTimeseriesPoint[]>(`/analytics/carrier-inflation/timeseries?horizon=${horizon}`),
        fetchFromApi<CorridorItem[]>("/routes"),
      ]);

      if (inf) setInflationData(inf);
      if (ts) setTimeseries(ts);
      if (rts) setCorridors(rts);
      setLoading(false);
    }
    loadData();
  }, [horizon]);

  const chartSeries: SeriesConfig[] = [
    { key: "6E", name: "IndiGo (6E)", color: "#38bdf8", strokeWidth: 2.5 },
    { key: "AI", name: "Air India (AI)", color: "#f97316", strokeWidth: 2.5 },
    { key: "SG", name: "SpiceJet (SG)", color: "#f59e0b", strokeWidth: 2 },
    { key: "QP", name: "Akasa Air (QP)", color: "#a855f7", strokeWidth: 2 },
  ];

  const carriers = inflationData?.carriers || [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <SectionHeader
        title="Phoenix Carrier Inflation Dynamics"
        headline="Tracking airline yield trajectories, pricing power variations, and econometric inflation trends across Indian domestic operators."
        badge="PHOENIX CARRIER INTELLIGENCE"
        badgeVariant="solid"
        action={
          <div className="flex items-center gap-1.5 rounded-[18px] border border-hairline bg-canvas p-1">
            {([1, 7, 15, 30, 45] as const).map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`rounded-[18px] px-3.5 py-1.5 text-xs font-sans font-medium transition-all ${
                  horizon === h
                    ? "bg-ink text-paper shadow-subtle"
                    : "text-mid-gray hover:text-ink"
                }`}
              >
                T+{h}
              </button>
            ))}
          </div>
        }
      />

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Inter-Airline Spread"
          value={inflationData ? `${inflationData.carrier_inflation_spread.toFixed(1)} pts` : "—"}
          subtitle="Max - Min airline price index delta"
          icon={<Scale className="h-6 w-6" />}
          badge="Price Dispersion"
        />

        <StatCard
          title="Inflation Pace Leader"
          value={inflationData?.inflation_leader || "—"}
          subtitle="Carrier with highest relative price level"
          icon={<TrendingUp className="h-6 w-6" />}
          badge="Price Leader"
        />

        <StatCard
          title="Value Competitive Leader"
          value={inflationData?.value_leader || "—"}
          subtitle="Most competitive lowest-economy quotes"
          icon={<Plane className="h-6 w-6" />}
          badge="Value Index"
        />

        <StatCard
          title="Monitored Fleet"
          value={`${carriers.length} Airlines`}
          subtitle="IndiGo, Air India, SpiceJet, Akasa Air"
          icon={<Layers className="h-6 w-6" />}
          badge={`Anchor T+${horizon}`}
        />
      </div>

      {/* Airline Comparative Scorecards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {carriers.map((c) => {
          return (
            <div
              key={c.carrier_code}
              className="rounded-cards border border-hairline bg-paper p-5 transition-all hover:border-mid-gray shadow-subtle"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold px-2 py-0.5 rounded-[6px] bg-canvas border border-hairline text-ink">
                    {c.carrier_code}
                  </span>
                  <span className="font-sans font-semibold text-sm text-ink">
                    {c.carrier_name}
                  </span>
                </div>
                <Badge variant="secondary" size="sm">
                  {c.routes_covered} Routes
                </Badge>
              </div>

              <div className="mt-4">
                <div className="text-3xl font-semibold font-sans text-ink tracking-[-0.75px]">
                  {c.index_value.toFixed(1)}
                </div>
                <div className="text-[11px] font-sans text-mid-gray mt-0.5">
                  Base: 2026-08-01 = 100.0
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-hairline text-center font-sans text-xs">
                <div>
                  <div className="text-[10px] text-mid-gray uppercase font-medium">1-Day</div>
                  <div className="font-semibold text-ink mt-0.5">
                    {c.daily_change_pct >= 0 ? "+" : ""}{c.daily_change_pct.toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-mid-gray uppercase font-medium">7-Day</div>
                  <div className="font-semibold text-ink mt-0.5">
                    {c.weekly_change_pct >= 0 ? "+" : ""}{c.weekly_change_pct.toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-mid-gray uppercase font-medium">30-Day</div>
                  <div className="font-semibold text-ink mt-0.5">
                    {c.monthly_change_pct >= 0 ? "+" : ""}{c.monthly_change_pct.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Comparative Timeseries Chart */}
      <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
              <TrendingUp className="h-4 w-4 text-ink" />
              Comparative Carrier Inflation Trajectory
            </h3>
            <p className="text-xs text-mid-gray font-sans mt-0.5">
              Daily Laspeyres index progression for each airline on horizon T+{horizon}, weighted by DGCA route volumes.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-sans">
            <span className="flex items-center gap-1.5 text-ink">
              <span className="h-2 w-2 rounded-full bg-ink" /> IndiGo
            </span>
            <span className="flex items-center gap-1.5 text-mid-gray">
              <span className="h-2 w-2 rounded-full bg-[#404040]" /> Air India
            </span>
            <span className="flex items-center gap-1.5 text-mid-gray">
              <span className="h-2 w-2 rounded-full bg-[#737373]" /> SpiceJet
            </span>
            <span className="flex items-center gap-1.5 text-mid-gray">
              <span className="h-2 w-2 rounded-full bg-[#a3a3a3]" /> Akasa Air
            </span>
          </div>
        </div>

        {timeseries.length > 0 ? (
          <LineChart
            data={timeseries}
            xKey="date"
            series={chartSeries}
            height={320}
            yDomain={["auto", "auto"]}
            valueSuffix=" pts"
          />
        ) : (
          <div className="h-72 flex flex-col items-center justify-center text-center p-6 border border-dashed border-hairline rounded-nested bg-canvas">
            <Calendar className="h-8 w-8 text-mid-gray mb-2" />
            <div className="font-sans font-semibold text-sm text-ink">Building Multi-Day Carrier Timeseries</div>
            <div className="font-sans text-xs text-mid-gray max-w-md mt-1">
              Carrier inflation indices are recorded at each scheduled 18:00 IST closing quote. Historical comparative chart will expand as daily cycles accumulate.
            </div>
          </div>
        )}
      </div>

      {/* Econometric Methodology Callout */}
      <div className="rounded-nested border border-hairline bg-canvas p-6">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-ink shrink-0 mt-0.5" />
          <div className="space-y-2 text-xs font-sans text-mid-gray leading-relaxed">
            <div className="font-semibold text-sm text-ink">
              MoSPI Statistical Standards: Why Carrier-Level Inflation Must Be Isolated
            </div>
            <p>
              In airline duopolies and oligopolies, pooling fares across carriers obscures individual pricing power and tacit collusion. Airline revenue management algorithms adjust fare classes independently.
            </p>
            <p>
              By computing an isolated Laspeyres index for each carrier using DGCA-weighted route baskets, the observatory identifies which airlines are driving cost-push inflation versus discounting to defend market share.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
