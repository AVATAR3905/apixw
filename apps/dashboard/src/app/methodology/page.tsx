"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Tooltip } from "@/components/ui/Tooltip";
import { PrototypePill } from "@/components/ui/PrototypePill";
import { 
  FileText, 
  ShieldAlert, 
  BookOpen, 
  Layers, 
  CheckCircle2, 
  Percent, 
  Sigma,
  Scale,
  ShieldCheck,
  AlertTriangle
} from "lucide-react";

export default function MethodologyPage() {
  const basket = [
    { code: "DEL-BOM", name: "Delhi ↔ Mumbai", vol: "3,250,000", weight: 18.4, type: "Trunk Metro" },
    { code: "DEL-BLR", name: "Delhi ↔ Bengaluru", vol: "2,510,000", weight: 14.2, type: "Trunk Metro" },
    { code: "BOM-BLR", name: "Mumbai ↔ Bengaluru", vol: "2,140,000", weight: 12.1, type: "Trunk Metro" },
    { code: "DEL-CCU", name: "Delhi ↔ Kolkata", vol: "1,850,000", weight: 10.5, type: "Trunk Metro" },
    { code: "DEL-HYD", name: "Delhi ↔ Hyderabad", vol: "1,730,000", weight: 9.8, type: "Trunk Metro" },
    { code: "BOM-MAA", name: "Mumbai ↔ Chennai", vol: "1,520,000", weight: 8.6, type: "Trunk Metro" },
    { code: "BLR-HYD", name: "Bengaluru ↔ Hyderabad", vol: "1,390,000", weight: 7.9, type: "Trunk Metro" },
    { code: "DEL-MAA", name: "Delhi ↔ Chennai", vol: "1,320,000", weight: 7.5, type: "Trunk Metro" },
    { code: "DEL-IXS", name: "Delhi ↔ Silchar", vol: "1,020,000", weight: 5.8, type: "Thin Regional" },
    { code: "DEL-DHM", name: "Delhi ↔ Dharamshala", vol: "920,000", weight: 5.2, type: "Thin Regional" },
  ];

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Page Header */}
      <SectionHeader
        title="Statistical Methodology & Governance"
        headline="Formal mathematical framework, basket weighting derivation, estimator guarantees, and documented limitations for APIX-2.0."
        badge="APIX-2.0 SPECIFICATION"
        badgeVariant="soft"
        action={
          <div className="flex items-center gap-2 font-mono text-xs text-ink bg-paper px-3.5 py-1.5 rounded-[18px] border border-hairline shadow-subtle">
            <BookOpen className="h-4 w-4 text-ink" />
            <span className="font-semibold">MoSPI COMPLIANT SPECIFICATION</span>
          </div>
        }
      />

      {/* Section 1: Mathematical Formulation */}
      <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle space-y-5">
        <div className="flex items-center gap-2 text-ink">
          <Sigma className="h-5 w-5 text-ink" />
          <h2 className="text-lg font-bold text-ink font-sans">
            1. Modified Laspeyres Price Index Formulation
          </h2>
        </div>

        <p className="text-xs text-mid-gray leading-relaxed">
          The national headline airfare index measures relative price changes weighted by base-period passenger travel volumes, anchored at a standardized advance booking horizon:
        </p>

        {/* Formula Display Box */}
        <div className="rounded-nested border border-hairline bg-surface-alt p-6 font-mono text-center space-y-3">
          <div className="text-xl sm:text-2xl font-bold text-ink tracking-wide">
            I<sub>t</sub> = 100 × ∑ [ w<sub>j</sub> × ( P<sub>j, t, T+15</sub> / P<sub>j, 0, T+15</sub> ) ]
          </div>
          <div className="text-xs text-mid-gray">
            Where ∑ w<sub>j</sub> = 1.000 across all 10 monitored domestic corridors
          </div>
        </div>

        {/* Variable Definitions Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs font-mono">
          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <span className="text-ink font-bold">w_j (Route Weight)</span>
            <p className="text-mid-gray text-[11px] font-sans">
              Normalized quarterly passenger traffic weight of route j derived from official DGCA city-pair statistics.
            </p>
          </div>
          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <span className="text-ink font-bold">P_(j, t, T+15) (Current Price)</span>
            <p className="text-mid-gray text-[11px] font-sans">
              Cross-carrier median of lowest available basic economy fares observed on day t at the 15-day booking horizon.
            </p>
          </div>
          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <span className="text-ink font-bold">P_(j, 0, T+15) (Reference Base)</span>
            <p className="text-mid-gray text-[11px] font-sans">
              Reference price observed on baseline date (2026-08-01 = 100.00) under identical advance purchase conditions.
            </p>
          </div>
          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <span className="text-ink font-bold">T+15 Advance Anchor</span>
            <p className="text-mid-gray text-[11px] font-sans">
              Standardized 15-day booking window insulating the headline index from passenger mix shifts.
            </p>
          </div>
        </div>
      </div>

      {/* Section 2: Monitored Route Basket */}
      <div className="rounded-cards border border-hairline bg-paper shadow-subtle overflow-hidden">
        <div className="p-6 border-b border-hairline">
          <h2 className="text-lg font-bold text-ink font-sans">
            2. Monitored Basket & Normalized DGCA Weights (DGCA_2026_V1)
          </h2>
          <p className="text-xs text-mid-gray mt-0.5">
            10 selected corridors covering 8 high-density trunk routes and 2 price-vulnerable thin regional routes.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-hairline bg-surface-alt text-mid-gray uppercase tracking-wider text-[11px]">
                <th className="px-6 py-3.5 font-semibold">Corridor</th>
                <th className="px-6 py-3.5 font-semibold">Route Pair</th>
                <th className="px-6 py-3.5 font-semibold">Corridor Type</th>
                <th className="px-6 py-3.5 font-semibold">Quarterly Passengers</th>
                <th className="px-6 py-3.5 font-semibold text-right">Normalized Weight</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline/60 font-sans text-xs">
              {basket.map((r) => (
                <tr key={r.code} className="hover:bg-canvas transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-ink">{r.code}</td>
                  <td className="px-6 py-4 text-ink font-medium">{r.name}</td>
                  <td className="px-6 py-4">
                    <Badge variant={r.type === "Trunk Metro" ? "soft" : "solid"} size="xs">
                      {r.type}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 font-mono text-mid-gray">{r.vol}</td>
                  <td className="px-6 py-4 text-right">
                    <div className="font-mono font-bold text-ink text-sm">{r.weight.toFixed(1)}%</div>
                    <div className="w-24 ml-auto bg-canvas rounded-full h-1 mt-1 overflow-hidden border border-hairline">
                      <div
                        className="bg-ink h-full rounded-full"
                        style={{ width: `${r.weight * 5}%` }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 3: Four Core Methodological Guarantees */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-ink font-sans">
          3. Core Methodological Defense Guarantees
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-3">
            <div className="flex items-center gap-2 text-ink font-mono text-xs font-bold uppercase">
              <CheckCircle2 className="h-4 w-4 text-ink" />
              <span>Fare-Mix Confounding Defense</span>
            </div>
            <p className="text-xs text-mid-gray leading-relaxed font-sans">
              Standard aggregators compute a raw median across all airline fares. If a carrier introduces premium &quot;Flexi Plus&quot; fares or alters cabin class distributions, the raw median falsely spikes. APIX-2.0 extracts the lowest basic economy fare per airline first, then takes the cross-carrier median, mathematically neutralizing fare-mix distortion.
            </p>
          </div>

          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-3">
            <div className="flex items-center gap-2 text-ink font-mono text-xs font-bold uppercase">
              <ShieldCheck className="h-4 w-4 text-ink" />
              <span>Unpooled Advance Purchase Windows</span>
            </div>
            <p className="text-xs text-mid-gray leading-relaxed font-sans">
              Averaging T+1 and T+45 prices together confuses passenger booking timing shifts with true carrier tariff inflation. The Observatory maintains 5 independent lead-time series and fixes the national headline anchor at T+15 to prevent booking-mix contamination.
            </p>
          </div>

          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-3">
            <div className="flex items-center gap-2 text-ink font-mono text-xs font-bold uppercase">
              <Scale className="h-4 w-4 text-ink" />
              <span>Non-Zero Sold-Out Flight Isolation</span>
            </div>
            <p className="text-xs text-mid-gray leading-relaxed font-sans">
              When all basic seats on a flight sell out, naive parsers often record ₹0 or exclude the flight incorrectly. APIX-2.0 treats sold-out flights as unavailable observations, preventing artificial price deflation or distortion of representative medians.
            </p>
          </div>

          <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-3">
            <div className="flex items-center gap-2 text-ink font-mono text-xs font-bold uppercase">
              <AlertTriangle className="h-4 w-4 text-ink" />
              <span>Documented Weighting Limitations</span>
            </div>
            <p className="text-xs text-mid-gray leading-relaxed font-sans">
              DGCA passenger volume weights reflect boarded passengers rather than vulnerable regional route pricing. Highly competitive trunk corridors receive heavy weights (DEL-BOM: 18.4%), while price-vulnerable thin corridors receive smaller weights (DEL-IXS: 5.8%). Users should examine route-level sub-indices alongside the aggregate.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
