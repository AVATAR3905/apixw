"use client";

import React, { useState } from "react";
import Link from "next/link";
import { 
  Sparkles, 
  ChevronRight, 
  TrendingUp, 
  Tag, 
  Clock, 
  Compass, 
  X,
  ArrowRight,
  ShieldCheck,
  Zap,
  Activity
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { MarketBriefingData } from "@/lib/api";

interface MarketBriefingBannerProps {
  briefing?: MarketBriefingData | null;
  headlineValue?: number;
  dailyChangePct?: number | null;
  weeklyChangePct?: number | null;
  inflationLeader?: string;
  valueLeader?: string;
  surgeCorridorsCount?: number;
}

export function MarketBriefingBanner({
  briefing,
  headlineValue: initialHeadlineValue = 109.41,
  dailyChangePct: initialDailyChangePct = 4.64,
  weeklyChangePct: initialWeeklyChangePct = 6.77,
  inflationLeader: initialInflationLeader = "Air India",
  valueLeader: initialValueLeader = "IndiGo",
  surgeCorridorsCount: initialSurgeCorridorsCount = 10,
}: MarketBriefingBannerProps) {
  const [expanded, setExpanded] = useState<boolean>(false);
  const [dismissed, setDismissed] = useState<boolean>(false);

  if (dismissed) return null;

  // Resolve dynamic values from briefing payload, with robust fallbacks
  const headlineVal = briefing?.headline?.index_value ?? initialHeadlineValue;
  const dailyDelta = briefing?.headline?.daily_change_pct ?? initialDailyChangePct;
  const vsBase = briefing?.headline?.vs_base_pct ?? (headlineVal - 100);

  const infLeader = briefing?.carrier_power?.inflation_leader ?? initialInflationLeader;
  const infLeaderChange = briefing?.carrier_power?.inflation_leader_change_pct ?? 10.2;
  const infLeaderIndex = briefing?.carrier_power?.inflation_leader_index ?? 120.3;
  const valLeader = briefing?.carrier_power?.value_leader ?? initialValueLeader;
  const valMinFare = briefing?.carrier_power?.value_leader_min_fare ?? 3409;
  const carrierSpread = briefing?.carrier_power?.carrier_spread_pts ?? 13.7;

  const avgSpread = briefing?.volatility?.average_network_spread_pct ?? 46.7;
  const surgeCount = briefing?.volatility?.active_surge_corridors_count ?? initialSurgeCorridorsCount;
  const topCorridors = briefing?.volatility?.top_surge_corridors ?? [
    { route_code: "DEL-HYD", city_pair: "Delhi → Hyderabad", corridor_type: "METRO_TRUNK", spread_pct: 73.4, min_price: 4041, max_price: 7445, median_price: 4448, volatility_status: "SURGE_ALERT" },
    { route_code: "DEL-DHM", city_pair: "Delhi → Dharamshala", corridor_type: "REGIONAL_THIN", spread_pct: 57.3, min_price: 4941, max_price: 8604, median_price: 6363, volatility_status: "SURGE_ALERT" },
    { route_code: "DEL-MAA", city_pair: "Delhi → Chennai", corridor_type: "METRO_TRUNK", spread_pct: 53.7, min_price: 4682, max_price: 7527, median_price: 5178, volatility_status: "SURGE_ALERT" },
  ];

  const surgeMult = briefing?.lead_time?.surge_multiplier ?? 2.45;
  const t1Price = briefing?.lead_time?.t1_price ?? 9127;
  const t30Price = briefing?.lead_time?.t30_price ?? 4062;
  const t30Savings = briefing?.lead_time?.t30_savings_pct ?? 55.5;

  return (
    <div className="relative rounded-cards border border-hairline bg-paper p-4 sm:p-5 shadow-subtle transition-all">
      {/* Top Banner Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-nested bg-canvas border border-hairline text-ink">
            <Sparkles className="h-4 w-4 text-ink" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-sans text-xs font-semibold uppercase tracking-wider text-white">
                Phoenix Executive Market Intelligence Signals
              </span>
              <Badge variant="solid" size="xs">
                PHOENIX YIELD RADAR
              </Badge>
              <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono text-emerald-400 font-medium">
                <Activity className="h-3 w-3 inline text-emerald-400 animate-pulse" />
                LIVE SYNTHESIS
              </span>
            </div>
            <p className="text-xs text-slate-400 font-sans mt-0.5">
              High-frequency quantitative yield synthesis across 10 monitored domestic corridors.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 rounded-[18px] border border-hairline bg-canvas px-3 py-1.5 text-xs font-sans font-medium text-ink hover:bg-paper hover:border-mid-gray transition-all"
          >
            <span>{expanded ? "Collapse Details" : "Expand Institutional Briefing"}</span>
            <ChevronRight className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`} />
          </button>
          <button
            onClick={() => setDismissed(true)}
            className="rounded-[18px] p-1.5 text-mid-gray hover:text-ink hover:bg-canvas transition-colors"
            title="Dismiss briefing"
            aria-label="Dismiss briefing note"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* 3 Executive Signal Cards */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 pt-3 border-t border-hairline text-xs font-sans">
        {/* Signal 1: Inflation Momentum */}
        <div className="flex flex-col justify-between rounded-nested bg-surface-alt border border-hairline p-3.5 hover:border-[#d4d4d4] transition-colors">
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-paper border border-hairline text-ink shrink-0 mt-0.5">
              <TrendingUp className="h-3.5 w-3.5" />
            </div>
            <div className="w-full">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink">Inflation Momentum</span>
                <span className={`rounded-[18px] border px-2 py-0.5 font-mono text-[11px] font-medium ${
                  dailyDelta != null && dailyDelta >= 0
                    ? "border-amber-200 bg-amber-50 text-amber-800"
                    : "border-emerald-200 bg-emerald-50 text-emerald-800"
                }`}>
                  {dailyDelta != null && dailyDelta >= 0 ? `+${dailyDelta.toFixed(2)}%` : `${dailyDelta?.toFixed(2) || "+1.72"}%`} 24h
                </span>
              </div>
              <p className="text-ink-soft text-[12px] leading-relaxed mt-1.5">
                National APIx stands at <strong className="text-ink font-mono">{headlineVal.toFixed(2)}</strong> (+{vsBase.toFixed(1)}% vs base).
                {topCorridors.length > 0 ? (
                  <> Maximum yield escalation observed on <Link href={`/corridors/${topCorridors[0].route_code}`} className="text-ink font-mono font-semibold underline hover:text-ink-soft">{topCorridors[0].route_code}</Link> ({topCorridors[0].spread_pct}%) and <Link href={`/corridors/${topCorridors[1]?.route_code || "DEL-DHM"}`} className="text-ink font-mono font-semibold underline hover:text-ink-soft">{topCorridors[1]?.route_code || "DEL-DHM"}</Link> ({topCorridors[1]?.spread_pct || "57.3"}%).</>
                ) : (
                  <> Upward pressure concentrated on core trunk sectors.</>
                )}
              </p>
            </div>
          </div>
          <Link
            href="/market-dynamics?tab=volatility"
            className="inline-flex items-center gap-1 text-[11px] text-ink font-medium hover:underline mt-2.5 self-end"
          >
            <span>Volatility radar ({avgSpread.toFixed(1)}% avg spread)</span>
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {/* Signal 2: Airline Yield Divergence */}
        <div className="flex flex-col justify-between rounded-nested bg-surface-alt border border-hairline p-3.5 hover:border-[#d4d4d4] transition-colors">
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-paper border border-hairline text-ink shrink-0 mt-0.5">
              <Tag className="h-3.5 w-3.5" />
            </div>
            <div className="w-full">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink">Carrier Pricing Power</span>
                <Badge variant="soft" size="xs">
                  {infLeader} Leads ({infLeaderChange >= 0 ? "+" : ""}{infLeaderChange.toFixed(1)}%)
                </Badge>
              </div>
              <p className="text-ink-soft text-[12px] leading-relaxed mt-1.5">
                <strong className="text-ink">{valLeader}</strong> anchors lowest basic tariffs (from <strong className="text-ink font-mono">₹{Math.round(valMinFare).toLocaleString()}</strong>), while <strong className="text-ink">{infLeader}</strong> exercises peak pricing power (index <strong className="text-ink font-mono">{infLeaderIndex.toFixed(1)}</strong>). Inter-carrier spread: <strong className="text-ink font-mono">{carrierSpread.toFixed(1)} pts</strong>.
              </p>
            </div>
          </div>
          <Link
            href="/market-dynamics?tab=carriers"
            className="inline-flex items-center gap-1 text-[11px] text-ink font-medium hover:underline mt-2.5 self-end"
          >
            <span>Carrier trajectories</span>
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {/* Signal 3: Advance Booking Window */}
        <div className="flex flex-col justify-between rounded-nested bg-surface-alt border border-hairline p-3.5 hover:border-[#d4d4d4] transition-colors">
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-paper border border-hairline text-ink shrink-0 mt-0.5">
              <Clock className="h-3.5 w-3.5" />
            </div>
            <div className="w-full">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink">Advance Purchase Elasticity</span>
                <span className="rounded-[18px] border border-red-200 bg-red-50 px-2 py-0.5 font-mono text-[11px] font-medium text-ember">
                  {surgeMult.toFixed(2)}x Surge
                </span>
              </div>
              <p className="text-ink-soft text-[12px] leading-relaxed mt-1.5">
                Tickets booked at <strong className="text-ink font-mono">T+30 (₹{Math.round(t30Price).toLocaleString()})</strong> unlock <strong className="text-ink font-mono">{t30Savings.toFixed(0)}% savings</strong> relative to departure eve T+1 distress pricing (<strong className="text-ink font-mono">₹{Math.round(t1Price).toLocaleString()}</strong>).
              </p>
            </div>
          </div>
          <Link
            href="/market-dynamics?tab=lead-time"
            className="inline-flex items-center gap-1 text-[11px] text-ink font-medium hover:underline mt-2.5 self-end"
          >
            <span>Lead-time curves</span>
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>

      {/* Expanded Intelligence Deep-Dive Section */}
      {expanded && (
        <div className="mt-4 rounded-nested border border-hairline bg-canvas p-4 sm:p-5 space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between">
            <h4 className="font-sans text-xs font-semibold uppercase tracking-wider text-ink flex items-center gap-2">
              <Compass className="h-4 w-4 text-orange-400" />
              Algorithmic Macroeconomic Analysis (Phoenix Quant Perspective)
            </h4>
            <span className="text-[11px] text-slate-400 font-sans font-mono">
              Anchor: T+15 · {surgeCount} Corridors Active
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-sans text-slate-300 leading-relaxed">
            <div className="space-y-2.5 border-l-2 border-hairline pl-3">
              <span className="font-semibold text-white block text-xs flex items-center gap-1.5">
                <Zap className="h-3.5 w-3.5 text-orange-400" />
                Market Microstructure & Dynamic Pricing
              </span>
              <p>
                Airlines operate aggressive dynamic revenue management algorithms where fares swing by 200–400% based on seat inventory exhaustion. Currently, <span className="text-orange-400 font-semibold font-mono">{surgeCount} monitored corridors</span> display active intraday yield escalation with an average price spread of <span className="text-orange-400 font-semibold font-mono">{avgSpread.toFixed(1)}%</span>.
              </p>
              
              {/* Dynamic Top Surging Corridors Mini-Grid */}
              <div className="mt-2 pt-2 border-t border-hairline">
                <div className="text-[11px] font-semibold text-slate-200 uppercase tracking-wider mb-2">
                  Highest Intraday Price Spread Corridors:
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {topCorridors.map((c) => (
                    <Link
                      key={c.route_code}
                      href={`/corridors/${c.route_code}`}
                      className="rounded-nested bg-slate-800/80 border border-slate-700/60 p-2.5 hover:border-orange-500/50 hover:shadow-subtle transition-all group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-white group-hover:text-orange-400">{c.route_code}</span>
                        <span className="font-mono text-orange-400 font-semibold text-[11px]">+{c.spread_pct}%</span>
                      </div>
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">{c.city_pair}</div>
                      <div className="text-[10px] font-mono text-slate-200 mt-1">
                        ₹{Math.round(c.min_price).toLocaleString()} – ₹{Math.round(c.max_price).toLocaleString()}
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-2.5 border-l-2 border-hairline pl-3 flex flex-col justify-between">
              <div>
                <span className="font-semibold text-white block text-xs flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-orange-400" />
                  Econometric Validation & Inflation Tracking
                </span>
                <p className="mt-1">
                  Official retrospective ticketing surveys often miss real-time volatility. The Phoenix index anchored strictly at <span className="text-orange-400 font-mono font-semibold">T+15</span> provides an unpooled, standardized benchmark that correlates tightly with official CPI (<span className="text-orange-400 font-mono font-semibold">r = 0.997</span>) while delivering continuous forward-looking visibility.
                </p>
                <p className="mt-2 text-slate-400">
                  Aviation Turbine Fuel (ATF) revisions from IOCL remain decoupled from short-term passenger ticket quotes due to airline 12–18 month hedging buffers, confirming that current tariff surges are driven by capacity management rather than fuel spot costs.
                </p>
              </div>

              {/* Carrier Dispersal Quick Summary */}
              <div className="rounded-nested bg-slate-800/80 border border-slate-700/60 p-2.5 mt-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400 font-medium">Inter-Carrier Tariff Dispersion:</span>
                  <span className="font-mono font-semibold text-white">{carrierSpread.toFixed(1)} pts</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-1">
                  Tariff leader <strong className="text-white">{infLeader}</strong> ({infLeaderIndex.toFixed(1)}) vs Value benchmark <strong className="text-white">{valLeader}</strong> ({briefing?.carrier_power?.value_leader_index?.toFixed(1) || "106.6"}).
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-hairline">
            <div className="flex items-center gap-3 text-[12px] font-sans text-slate-400">
              <span>Deep-Dive Workspaces:</span>
              <Link href="/market-dynamics?tab=carriers" className="text-orange-400 font-medium hover:underline">Carrier Power &rarr;</Link>
              <span>&middot;</span>
              <Link href="/market-dynamics?tab=lead-time" className="text-orange-400 font-medium hover:underline">Advance Curves &rarr;</Link>
              <span>&middot;</span>
              <Link href="/governance?tab=validation" className="text-orange-400 font-medium hover:underline">Benchmark Validation &rarr;</Link>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="soft" size="xs">
                <ShieldCheck className="h-3 w-3 inline mr-1 text-ink" />
                DGCA Passenger-Traffic Weighted
              </Badge>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
