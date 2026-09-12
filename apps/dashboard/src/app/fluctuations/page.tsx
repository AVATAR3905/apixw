"use client";

import React, { useState, useEffect } from "react";
import { 
  fetchFromApi, 
  VolatilityResponse, 
  RouteTrajectoryResponse, 
  VolatilityCorridor 
} from "@/lib/api";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import { 
  BarChart3, 
  AlertTriangle, 
  Activity, 
  Clock, 
  ArrowUpDown, 
  ShieldAlert, 
  Compass, 
  Info,
  CheckCircle2
} from "lucide-react";

export default function PriceFluctuationsPage() {
  const [horizon, setHorizon] = useState<number>(15);
  const [volatilityData, setVolatilityData] = useState<VolatilityResponse | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<string>("DEL-BOM");
  const [routeQuotes, setRouteQuotes] = useState<RouteTrajectoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      const res = await fetchFromApi<VolatilityResponse>(`/analytics/volatility?horizon=${horizon}`);
      if (res) {
        setVolatilityData(res);
        if (res.corridors.length > 0 && !selectedRoute) {
          setSelectedRoute(res.corridors[0].route_code);
        }
      }
      setLoading(false);
    }
    loadData();
  }, [horizon]);

  useEffect(() => {
    async function loadRouteQuotes() {
      if (!selectedRoute) return;
      const res = await fetchFromApi<RouteTrajectoryResponse>(`/analytics/volatility/${selectedRoute}`);
      if (res) setRouteQuotes(res);
    }
    loadRouteQuotes();
  }, [selectedRoute]);

  const corridors = volatilityData?.corridors || [];
  const activeSurges = volatilityData?.active_surge_corridors_count || 0;
  const avgSpread = volatilityData?.average_network_spread_pct || 0.0;
  const highestSpreadCorridor = corridors.length > 0 ? corridors[0] : null;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <SectionHeader
        title="Domestic Flight Price Fluctuations & Volatility Radar"
        headline="Tracking intraday yield management swings, price velocity, and min-max fare dispersion across monitored Indian aviation corridors."
        badge="INTRADAY DISPERSION RADAR"
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

      {/* KPI StatCards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Average Network Spread"
          value={`${avgSpread.toFixed(1)}%`}
          subtitle="Mean (Max - Min) / Mean across network"
          icon={<ArrowUpDown className="h-6 w-6" />}
          badge="Intraday Dispersion"
        />

        <StatCard
          title="Active Surge Corridors"
          value={`${activeSurges} Routes`}
          subtitle="Corridors with spread > 12%"
          icon={<AlertTriangle className="h-6 w-6" />}
          badge={activeSurges > 0 ? "Surge Detected" : "Network Calm"}
        />

        <StatCard
          title="Highest Volatility Corridor"
          value={highestSpreadCorridor ? highestSpreadCorridor.route_code : "—"}
          subtitle={highestSpreadCorridor ? `${highestSpreadCorridor.spread_pct.toFixed(1)}% spread (${highestSpreadCorridor.origin} - ${highestSpreadCorridor.destination})` : "Awaiting data"}
          icon={<Activity className="h-6 w-6" />}
          badge="Peak Swings"
        />

        <StatCard
          title="Daily Sampling Frequencies"
          value="4 Snapshots"
          subtitle="06:00, 12:00, 18:00 (MoSPI), 23:00 IST"
          icon={<Clock className="h-6 w-6" />}
          badge="Diurnal Standard"
        />
      </div>

      {/* Multi-Corridor Volatility Matrix Table */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
              <BarChart3 className="h-4 w-4 text-ink" />
              Corridor Price Range & Intraday Dispersion Matrix
            </h3>
            <p className="text-xs text-mid-gray font-sans mt-0.5">
              Live price bounds, standard deviations (&sigma;), and surge status on horizon T+{horizon}.
            </p>
          </div>

          <div className="flex items-center gap-3 font-sans text-xs text-mid-gray">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-ink-soft" /> Calm (&lt;4%)</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-mid-gray" /> Moderate (4-12%)</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-600" /> High (12-22%)</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-ember" /> Surge (&gt;22%)</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas font-sans uppercase tracking-[0.6px] text-mid-gray text-[11px] font-medium">
                <th className="px-6 py-3.5">Corridor</th>
                <th className="px-6 py-3.5">Type</th>
                <th className="px-6 py-3.5">Lowest Quote</th>
                <th className="px-6 py-3.5">Median Quote</th>
                <th className="px-6 py-3.5">Peak Quote</th>
                <th className="px-6 py-3.5">Intraday Spread</th>
                <th className="px-6 py-3.5">Std Dev (&sigma;)</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {corridors.map((c) => {
                const isSelected = selectedRoute === c.route_code;
                const statusVariant = 
                  c.volatility_status === "CALM" ? "success" :
                  c.volatility_status === "MODERATE" ? "warning" :
                  c.volatility_status === "HIGH_VOLATILITY" ? "outline" : "danger";

                return (
                  <tr 
                    key={c.route_code}
                    onClick={() => setSelectedRoute(c.route_code)}
                    className={`cursor-pointer transition-colors ${
                      isSelected 
                        ? "bg-canvas border-l-2 border-l-ink" 
                        : "hover:bg-canvas"
                    }`}
                  >
                    <td className="px-6 py-4 font-mono font-semibold text-ink">
                      <div className="flex items-center gap-2">
                        <span>{c.route_code}</span>
                        <span className="text-[11px] font-sans font-normal text-mid-gray">
                          ({c.origin} &rarr; {c.destination})
                        </span>
                      </div>
                    </td>

                    <td className="px-6 py-4">
                      <Badge variant={c.corridor_type === "METRO_TRUNK" ? "secondary" : "outline"} size="sm">
                        {c.corridor_type === "METRO_TRUNK" ? "Trunk" : "Regional"}
                      </Badge>
                    </td>

                    <td className="px-6 py-4 font-mono font-semibold text-ink">
                      &#8377;{c.min_price.toLocaleString("en-IN")}
                    </td>

                    <td className="px-6 py-4 font-mono font-medium text-ink">
                      &#8377;{c.median_price.toLocaleString("en-IN")}
                    </td>

                    <td className="px-6 py-4 font-mono font-semibold text-ink">
                      &#8377;{c.max_price.toLocaleString("en-IN")}
                    </td>

                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-ink">{c.spread_pct.toFixed(1)}%</span>
                        <div className="w-16 bg-canvas rounded-full h-1.5 overflow-hidden border border-hairline">
                          <div 
                            className={`h-full rounded-full ${
                              c.spread_pct > 22 ? "bg-ember" : "bg-ink-soft"
                            }`}
                            style={{ width: `${Math.min(100, c.spread_pct * 2.5)}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    <td className="px-6 py-4 font-mono text-mid-gray">
                      &plusmn;&#8377;{c.std_dev.toLocaleString("en-IN")}
                    </td>

                    <td className="px-6 py-4">
                      <Badge variant={statusVariant} size="sm">
                        {c.volatility_status.replace("_", " ")}
                      </Badge>
                    </td>

                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedRoute(c.route_code);
                        }}
                        className="rounded-[18px] px-2.5 py-1 text-[11px] font-sans font-medium border border-hairline bg-canvas text-ink hover:bg-paper hover:border-mid-gray"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Corridor Flight Quotes Deep-Dive */}
      {selectedRoute && (
        <div className="rounded-cards border border-hairline bg-paper p-6 space-y-4 shadow-subtle">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-hairline pb-4">
            <div>
              <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
                <Compass className="h-4 w-4 text-ink" />
                Individual Flight Quote Scatter for {selectedRoute}
              </h3>
              <p className="text-xs text-mid-gray font-sans mt-0.5">
                Authentic quotes sampled across IndiGo, Air India, SpiceJet, and Akasa Air.
              </p>
            </div>
            <div className="font-sans text-xs text-mid-gray">
              {routeQuotes?.quotes_count || 0} Authenticated Flight Observations
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 max-h-96 overflow-y-auto pr-1">
            {routeQuotes?.quotes.map((q, idx) => (
              <div 
                key={idx}
                className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-2 hover:border-mid-gray transition-all"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-ink">{q.flight_number}</span>
                  <Badge variant="secondary" size="sm">T+{q.advance_purchase_days}d</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-mid-gray font-sans">{q.carrier_name}</span>
                  <span className="font-mono text-sm font-semibold text-ink">&#8377;{q.base_fare.toLocaleString("en-IN")}</span>
                </div>
                <div className="flex items-center justify-between text-[10px] font-mono text-mid-gray pt-1 border-t border-hairline">
                  <span>{q.fare_family}</span>
                  <span>Total: &#8377;{q.total_fare.toLocaleString("en-IN")}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Educational Footnote */}
      <div className="rounded-nested border border-hairline bg-canvas p-6">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-ink shrink-0 mt-0.5" />
          <div className="space-y-2 text-xs font-sans text-mid-gray leading-relaxed">
            <div className="font-semibold text-sm text-ink">
              Statistical Methodology: Unconfounded Diurnal Sampling Standard
            </div>
            <p>
              Airlines run algorithmic revenue management systems that continually adjust seat inventory into tiered fare buckets. A morning business flight may be priced 30% higher than an afternoon leisure slot on the exact same corridor.
            </p>
            <p>
              To construct an official Laspeyres Headline Index compliant with MoSPI guidelines, pricing must be sampled at a standardized fixed closing hour (18:00 IST) to prevent diurnal noise from contaminating macro price signals. Meanwhile, intraday multi-snapshot spreads (06:00, 12:00, 18:00, 23:00 IST) provide consumer transparency into peak booking surges.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
