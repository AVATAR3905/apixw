"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { InfoTooltip } from "@/components/ui/Tooltip";
import { PrototypePill } from "@/components/ui/PrototypePill";
import { 
  ArrowRight, 
  Filter, 
  Flame, 
  ChevronRight, 
  ChevronDown, 
  Plane, 
  Sparkles,
  TrendingUp,
  Percent
} from "lucide-react";
import { fetchFromApi, CorridorItem } from "@/lib/api";

export default function RouteMatrixPage() {
  const [filterType, setFilterType] = useState<"ALL" | "METRO_TRUNK" | "REGIONAL_THIN">("ALL");
  const [expandedRoute, setExpandedRoute] = useState<string | null>("DEL-BOM");

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
            fare: "₹3,000+",
            status: c.corridor_type === "REGIONAL_THIN" ? "VOLATILE" : "NORMAL",
            carriers: "6E, AI, SG, QP",
            flights: 24,
          }))
        );
      }
    }
    loadCorridors();
  }, []);

  const filtered = corridors.filter((c) => filterType === "ALL" || c.type === filterType);

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <SectionHeader
        title="Domestic Corridor Matrix & Heatmap"
        headline="Monitored basket of 10 domestic aviation corridors, weighted strictly by official DGCA quarterly passenger volume statistics."
        badge="DGCA BASKET 2026_V1"
        badgeVariant="solid"
        action={
          <div className="flex items-center gap-1.5 rounded-[18px] border border-hairline bg-canvas p-1">
            {(["ALL", "METRO_TRUNK", "REGIONAL_THIN"] as const).map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`rounded-[18px] px-3.5 py-1.5 text-xs font-sans font-medium transition-all ${
                  filterType === type
                    ? "bg-ink text-paper shadow-subtle"
                    : "text-mid-gray hover:text-ink"
                }`}
              >
                {type === "ALL" ? "All Corridors (10)" : type === "METRO_TRUNK" ? "Trunk Metro (8)" : "Thin Regional (2)"}
              </button>
            ))}
          </div>
        }
      />

      {/* Heatmap Spectrum Ribbon */}
      <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-ink" />
            <span className="font-sans font-semibold text-sm text-ink">
              7-Day Price Pressure Heatmap
            </span>
            <InfoTooltip
              label="Weekly Momentum"
              tooltip="Corridors ranked by rate of price escalation over the past 7 days."
            />
          </div>
          <span className="text-[11px] font-sans text-mid-gray">Range: +2.4% (Calm) to +7.6% (Surging)</span>
        </div>

        {/* Heatmap visual chips */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
          {corridors
            .slice()
            .sort((a, b) => parseFloat(b.d7) - parseFloat(a.d7))
            .map((c) => {
              const isHigh = parseFloat(c.d7) >= 5.0;
              return (
                <div
                  key={c.code}
                  onClick={() => setExpandedRoute(expandedRoute === c.code ? null : c.code)}
                  className={`p-3 rounded-nested border cursor-pointer transition-all ${
                    isHigh
                      ? "border-mid-gray bg-canvas"
                      : "border-hairline bg-canvas hover:border-mid-gray"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-xs text-ink">{c.code}</span>
                    <span className="font-mono text-xs font-semibold text-ink">
                      {c.d7}
                    </span>
                  </div>
                  <div className="mt-1 text-[11px] text-mid-gray truncate font-sans">{c.name}</div>
                  <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-mid-gray">
                    <span>Index {c.idx}</span>
                    <span>{c.fare}</span>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Corridor Table */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="px-6 py-4 border-b border-hairline flex items-center justify-between bg-paper">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-ink font-sans">Corridor Catalog & Diagnostics</span>
            <PrototypePill />
          </div>
          <span className="text-xs font-sans text-mid-gray">Click any row to expand details</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas text-mid-gray font-sans uppercase tracking-[0.6px] text-[11px]">
                <th className="px-6 py-3.5 font-medium">Corridor</th>
                <th className="px-6 py-3.5 font-medium">Classification</th>
                <th className="px-6 py-3.5 font-medium">DGCA Weight</th>
                <th className="px-6 py-3.5 font-medium">Median Base Fare</th>
                <th className="px-6 py-3.5 font-medium">Route Index (T+15)</th>
                <th className="px-6 py-3.5 font-medium">1-Day</th>
                <th className="px-6 py-3.5 font-medium">7-Day</th>
                <th className="px-6 py-3.5 font-medium">30-Day</th>
                <th className="px-6 py-3.5 font-medium text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {filtered.map((c) => {
                const isExpanded = expandedRoute === c.code;
                return (
                  <React.Fragment key={c.code}>
                    <tr
                      onClick={() => setExpandedRoute(isExpanded ? null : c.code)}
                      className={`cursor-pointer transition-colors ${
                        isExpanded ? "bg-canvas" : "hover:bg-canvas"
                      }`}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-ink shrink-0" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-mid-gray shrink-0" />
                          )}
                          <div>
                            <div className="font-mono font-semibold text-ink text-sm">{c.code}</div>
                            <div className="text-[11px] text-mid-gray font-sans">{c.name}</div>
                          </div>
                        </div>
                      </td>

                      <td className="px-6 py-4">
                        <Badge
                          variant={c.type === "METRO_TRUNK" ? "soft" : "outline"}
                          size="xs"
                        >
                          {c.type === "METRO_TRUNK" ? "Trunk Metro" : "Thin Regional"}
                        </Badge>
                      </td>

                      <td className="px-6 py-4">
                        <div className="font-sans font-medium text-ink">{c.weight.toFixed(1)}%</div>
                        <div className="w-16 bg-canvas rounded-full h-1 mt-1 overflow-hidden border border-hairline">
                          <div
                            className="bg-ink-soft h-full rounded-full"
                            style={{ width: `${c.weight * 5}%` }}
                          />
                        </div>
                      </td>

                      <td className="px-6 py-4 font-mono font-semibold text-ink text-sm">{c.fare}</td>

                      <td className="px-6 py-4">
                        <span className="font-mono font-semibold text-ink text-sm">{c.idx}</span>
                      </td>

                      <td className="px-6 py-4 font-mono text-mid-gray font-medium">{c.d1}</td>
                      <td className="px-6 py-4 font-mono text-ink font-semibold">{c.d7}</td>
                      <td className="px-6 py-4 font-mono text-ink font-semibold">{c.d30}</td>

                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/routes/${c.code}`}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1.5 rounded-[18px] border border-hairline bg-canvas px-2.5 py-1 text-xs font-medium text-ink hover:bg-paper hover:border-mid-gray transition-colors"
                        >
                          <span>Inspect</span>
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>

                    {/* Expandable row content */}
                    {isExpanded && (
                      <tr className="bg-canvas border-b border-hairline">
                        <td colSpan={9} className="px-6 py-4">
                          <div className="rounded-nested border border-hairline bg-paper p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-subtle">
                            <div className="space-y-1">
                              <div className="text-xs font-semibold text-ink flex items-center gap-2">
                                <Plane className="h-4 w-4 text-ink" />
                                <span>{c.name} ({c.airports}) Aviation Dynamics</span>
                              </div>
                              <p className="text-xs text-mid-gray max-w-xl font-sans">
                                Monitored across {c.carriers} with ~{c.flights} daily nonstop scheduled flights. Base fare relative is indexed against the August 1, 2026 reference anchor.
                              </p>
                            </div>

                            <div className="flex items-center gap-4 text-xs font-sans">
                              <div className="rounded-nested border border-hairline bg-canvas p-2.5">
                                <div className="text-mid-gray text-[10px] uppercase font-medium">Daily Flights</div>
                                <div className="text-ink font-semibold mt-0.5">{c.flights} Scheduled</div>
                              </div>
                              <div className="rounded-nested border border-hairline bg-canvas p-2.5">
                                <div className="text-mid-gray text-[10px] uppercase font-medium">Carriers Tracked</div>
                                <div className="text-ink font-semibold mt-0.5">{c.carriers}</div>
                              </div>
                              <Link
                                href={`/routes/${c.code}`}
                                className="inline-flex items-center gap-1.5 rounded-[18px] bg-ink px-4 py-2.5 text-xs font-medium text-paper hover:bg-ink-soft transition-colors shadow-subtle"
                              >
                                <span>Complete Fare Anatomy</span>
                                <ArrowRight className="h-3.5 w-3.5" />
                              </Link>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
