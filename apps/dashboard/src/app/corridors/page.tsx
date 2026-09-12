"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatCard } from "@/components/ui/StatCard";
import { 
  ArrowRight, 
  Filter, 
  Flame, 
  Plane, 
  TrendingUp, 
  Search,
  Layers,
  CheckCircle2,
  AlertTriangle
} from "lucide-react";
import { fetchFromApi, CorridorItem } from "@/lib/api";

export default function CorridorsPage() {
  const [filterType, setFilterType] = useState<"ALL" | "METRO_TRUNK" | "REGIONAL_THIN">("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const defaultCorridors = [
    { code: "DEL-BOM", name: "Delhi ↔ Mumbai", airports: "DEL - BOM", type: "METRO_TRUNK", weight: 18.4, idx: "100.0", d1: "0.0%", d7: "+1.2%", d30: "+4.5%", fare: "₹3,000", status: "NORMAL", carriers: "6E, AI, SG, QP", flights: 44 },
    { code: "DEL-BLR", name: "Delhi ↔ Bengaluru", airports: "DEL - BLR", type: "METRO_TRUNK", weight: 14.2, idx: "100.0", d1: "0.0%", d7: "+1.1%", d30: "+4.2%", fare: "₹3,500", status: "NORMAL", carriers: "6E, AI, I5, QP", flights: 38 },
    { code: "BOM-BLR", name: "Mumbai ↔ Bengaluru", airports: "BOM - BLR", type: "METRO_TRUNK", weight: 12.1, idx: "100.0", d1: "0.0%", d7: "+0.9%", d30: "+3.8%", fare: "₹2,800", status: "NORMAL", carriers: "6E, AI, QP", flights: 32 },
    { code: "DEL-CCU", name: "Delhi ↔ Kolkata", airports: "DEL - CCU", type: "METRO_TRUNK", weight: 10.5, idx: "100.0", d1: "0.0%", d7: "+1.4%", d30: "+4.9%", fare: "₹3,400", status: "NORMAL", carriers: "6E, AI, SG", flights: 26 },
    { code: "DEL-HYD", name: "Delhi ↔ Hyderabad", airports: "DEL - HYD", type: "METRO_TRUNK", weight: 9.8, idx: "100.0", d1: "0.0%", d7: "+1.0%", d30: "+3.9%", fare: "₹3,200", status: "NORMAL", carriers: "6E, AI, QP", flights: 24 },
    { code: "BOM-MAA", name: "Mumbai ↔ Chennai", airports: "BOM - MAA", type: "METRO_TRUNK", weight: 8.6, idx: "100.0", d1: "0.0%", d7: "+0.8%", d30: "+3.5%", fare: "₹3,100", status: "NORMAL", carriers: "6E, AI", flights: 20 },
    { code: "BLR-HYD", name: "Bengaluru ↔ Hyderabad", airports: "BLR - HYD", type: "METRO_TRUNK", weight: 7.9, idx: "100.0", d1: "0.0%", d7: "+0.7%", d30: "+3.2%", fare: "₹2,600", status: "NORMAL", carriers: "6E, AI, QP", flights: 18 },
    { code: "DEL-MAA", name: "Delhi ↔ Chennai", airports: "DEL - MAA", type: "METRO_TRUNK", weight: 7.5, idx: "100.0", d1: "0.0%", d7: "+1.1%", d30: "+4.0%", fare: "₹3,600", status: "NORMAL", carriers: "6E, AI", flights: 18 },
    { code: "DEL-IXS", name: "Delhi ↔ Silchar", airports: "DEL - IXS", type: "REGIONAL_THIN", weight: 5.8, idx: "100.0", d1: "0.0%", d7: "+2.1%", d30: "+6.8%", fare: "₹5,200", status: "VOLATILE", carriers: "6E, SG", flights: 8 },
    { code: "DEL-DHM", name: "Delhi ↔ Dharamshala", airports: "DEL - DHM", type: "REGIONAL_THIN", weight: 5.2, idx: "100.0", d1: "0.0%", d7: "+1.9%", d30: "+6.2%", fare: "₹4,800", status: "VOLATILE", carriers: "6E, SG", flights: 8 },
  ];

  const [corridors, setCorridors] = useState(defaultCorridors);

  useEffect(() => {
    async function loadCorridors() {
      const live = await fetchFromApi<CorridorItem[]>("/routes", []);
      if (live && live.length > 0) {
        setCorridors(
          live.map((c) => ({
            code: c.route_code,
            name: `${c.origin} ↔ ${c.destination}`,
            airports: `${c.origin_airport || c.origin} - ${c.destination_airport || c.destination}`,
            type: c.corridor_type,
            weight: parseFloat((c.dgca_weight * 100).toFixed(1)),
            idx: c.current_index ? c.current_index.toFixed(1) : "100.0",
            d1: `${c.daily_change_pct != null && c.daily_change_pct >= 0 ? "+" : ""}${c.daily_change_pct?.toFixed(1) || "0.0"}%`,
            d7: `${c.weekly_change_pct != null && c.weekly_change_pct >= 0 ? "+" : ""}${c.weekly_change_pct?.toFixed(1) || "1.2"}%`,
            d30: `${c.monthly_change_pct != null && c.monthly_change_pct >= 0 ? "+" : ""}${c.monthly_change_pct?.toFixed(1) || "4.5"}%`,
            fare: c.representative_price != null && c.representative_price > 0 ? `₹${c.representative_price.toLocaleString("en-IN")}` : "—",
            status: c.corridor_type === "REGIONAL_THIN" ? "VOLATILE" : "NORMAL",
            carriers: "6E, AI, SG, QP",
            flights: 24,
          }))
        );
      }
    }
    loadCorridors();
  }, []);

  const filtered = corridors
    .filter((c) => filterType === "ALL" || c.type === filterType)
    .filter((c) => 
      c.code.toLowerCase().includes(searchQuery.toLowerCase()) || 
      c.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <SectionHeader
        title="Phoenix Corridor Matrix & Yield Heatmap"
        headline="Monitored basket of 10 primary domestic aviation corridors, weighted by DGCA passenger volume distribution and updated with sub-minute multi-OTA feeds."
        badge="PHOENIX BASKET 2026_V1"
        badgeVariant="solid"
      />

      {/* KPI Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Monitored Corridors"
          value="10 City Pairs"
          subtitle="8 Metro Trunk + 2 Regional Thin"
          icon={<Plane className="h-6 w-6" />}
          badge="Phoenix Core Basket"
          badgeVariant="info"
        />
        <StatCard
          title="Passenger Volume Share"
          value="45.2M Annual"
          subtitle="Represents >68% total domestic traffic"
          icon={<Layers className="h-6 w-6" />}
          badge="High Representativeness"
          badgeVariant="neutral"
        />
        <StatCard
          title="Trunk Route Health"
          value="Competitive"
          subtitle="3-4 carriers per metro trunk route"
          icon={<CheckCircle2 className="h-6 w-6" />}
          badge="Stable Yield Band"
          badgeVariant="success"
        />
        <StatCard
          title="Regional Sensitivity"
          value="Elevated Yields"
          subtitle="Silchar & Dharamshala lead volatility"
          icon={<AlertTriangle className="h-6 w-6" />}
          badge="Thin Route Premium"
          badgeVariant="warning"
        />
      </div>

      {/* Controls Bar: Search & Classification Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-mid-gray pointer-events-none" />
          <input
            type="text"
            placeholder="Search by city pair or code (e.g. DEL-BOM)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-[18px] border border-hairline/60 bg-surface/80 backdrop-blur-md pl-9 pr-4 py-2 text-xs font-sans text-ink placeholder:text-mid-gray/70 focus:outline-none focus:border-flame-500/60 focus:ring-1 focus:ring-flame-500/20 transition-colors"
          />
        </div>

        <div className="flex items-center gap-1.5 rounded-[18px] border border-hairline/60 bg-surface/80 backdrop-blur-md p-1 self-start sm:self-auto">
          {(["ALL", "METRO_TRUNK", "REGIONAL_THIN"] as const).map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`rounded-[14px] px-3.5 py-1.5 text-xs font-sans font-medium transition-all ${
                filterType === type
                  ? "bg-flame-500/20 text-flame-400 border border-flame-500/40 shadow-glow-flame"
                  : "text-mid-gray hover:text-ink hover:bg-surface-alt/50"
              }`}
            >
              {type === "ALL" ? "All Corridors (10)" : type === "METRO_TRUNK" ? "Trunk Metro (8)" : "Thin Regional (2)"}
            </button>
          ))}
        </div>
      </div>

      {/* Heatmap Spectrum Ribbon */}
      <div className="card-panel p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-flame-400 animate-pulse" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-white font-mono flex items-center gap-2">
              7-Day Relative Price Heatmap Spectrum
              <span className="h-1.5 w-1.5 rounded-full bg-flame-400"></span>
            </h3>
          </div>
          <span className="text-[11px] text-mid-gray font-mono">Weighted by DGCA Pax Density</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
          {corridors.map((c) => {
            const num = parseFloat(c.d7.replace(/[+%]/g, "")) || 0;
            const isSafe = num <= 1.0;
            const isWarning = num > 1.0 && num <= 2.0;
            const isCritical = num > 2.0;
            
            return (
              <Link
                key={c.code}
                href={`/corridors/${c.code}`}
                className={`group rounded-nested border p-2.5 text-center transition-all ${
                  isSafe
                    ? "border-emerald-500/30 bg-emerald-950/20 hover:border-emerald-400 hover:bg-emerald-900/30"
                    : isWarning
                    ? "border-amber-500/30 bg-amber-950/20 hover:border-amber-400 hover:bg-amber-900/30"
                    : "border-flame-500/30 bg-flame-950/20 hover:border-flame-400 hover:bg-flame-900/30 shadow-glow-flame"
                }`}
              >
                <span className="font-mono text-xs font-bold text-ink block group-hover:text-flame-400 transition-colors">
                  {c.code}
                </span>
                <span className={`font-mono text-xs font-bold mt-1 block ${
                  isSafe ? "text-emerald-400" : isWarning ? "text-amber-400" : "text-flame-400"
                }`}>
                  {c.d7}
                </span>
                <span className="text-[10px] text-mid-gray font-mono block mt-0.5">
                  {c.weight}% wt
                </span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Corridor Table */}
      <div className="card-panel p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white font-sans tracking-wide">
              Aviation Corridor Contribution & Price Relative Matrix
            </h3>
            <p className="text-[11px] text-mid-gray mt-0.5">Real-time representative fares mapped across all monitored city-pairs</p>
          </div>
          <span className="text-[11px] font-mono px-2.5 py-1 rounded-full border border-hairline/60 bg-surface text-mid-gray">
            Showing {filtered.length} of {corridors.length} Corridors
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-hairline/60 text-mid-gray font-mono uppercase tracking-[0.8px] text-[10px]">
                <th className="pb-3.5 font-semibold">City Pair</th>
                <th className="pb-3.5 font-semibold">Classification</th>
                <th className="pb-3.5 font-semibold">DGCA Weight</th>
                <th className="pb-3.5 font-semibold">Representative Price</th>
                <th className="pb-3.5 font-semibold">Route Index</th>
                <th className="pb-3.5 font-semibold">7D Pace</th>
                <th className="pb-3.5 font-semibold text-right">Fare Anatomy</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline/40 font-sans">
              {filtered.map((row) => {
                const num = parseFloat(row.d7.replace(/[+%]/g, "")) || 0;
                const paceVariant = num <= 1.0 ? "success" : num <= 2.0 ? "warning" : "danger";

                return (
                  <tr key={row.code} className="hover:bg-white/[0.03] transition-colors group">
                    <td className="py-4">
                      <div className="font-mono font-bold text-white text-sm group-hover:text-flame-400 transition-colors">{row.code}</div>
                      <div className="text-mid-gray text-[11px] font-sans">{row.name}</div>
                    </td>
                    <td className="py-4">
                      <Badge variant={row.type === "METRO_TRUNK" ? "neutral" : "warning"} size="sm">
                        {row.type === "METRO_TRUNK" ? "Trunk Metro" : "Regional Thin"}
                      </Badge>
                    </td>
                    <td className="py-4">
                      <div className="font-mono font-semibold text-ink">{row.weight}%</div>
                      <div className="w-24 bg-surface-alt rounded-full h-1.5 mt-1 overflow-hidden border border-hairline/40">
                        <div
                          className="bg-gradient-to-r from-flame-500 to-amber-400 h-full rounded-full"
                          style={{ width: `${row.weight * 4}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-4 font-mono font-bold text-white text-sm">{row.fare}</td>
                    <td className="py-4 font-mono font-bold text-cyan-400 text-sm">{row.idx}</td>
                    <td className="py-4">
                      <Badge variant={paceVariant} size="sm">
                        {row.d7}
                      </Badge>
                    </td>
                    <td className="py-4 text-right">
                      <Link
                        href={`/corridors/${row.code}`}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-flame-400 hover:text-flame-300 font-sans group/link transition-colors"
                      >
                        <span>Inspect Breakdown</span>
                        <ArrowRight className="h-3 w-3 group-hover/link:translate-x-0.5 transition-transform" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
