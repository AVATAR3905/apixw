"use client";

import React, { useState, useEffect } from "react";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Tooltip } from "@/components/ui/Tooltip";
import { PrototypePill } from "@/components/ui/PrototypePill";
import { LineChart } from "@/components/charts/LineChart";
import { Fuel, AlertCircle, Info, TrendingUp, DollarSign, Calendar } from "lucide-react";
import { fetchFromApi } from "@/lib/api";

export default function FuelContextPage() {
  const defaultSeries = [
    { date: "01 Aug", atf: 94200, atfIndex: 100.0, fareIndex: 100.0 },
    { date: "07 Aug", atf: 94500, atfIndex: 100.3, fareIndex: 101.8 },
    { date: "14 Aug", atf: 95100, atfIndex: 101.0, fareIndex: 103.4 },
    { date: "21 Aug", atf: 96200, atfIndex: 102.1, fareIndex: 105.8 },
    { date: "28 Aug", atf: 97800, atfIndex: 103.8, fareIndex: 108.4 },
  ];

  const [fuelSeries, setFuelSeries] = useState(defaultSeries);
  const [fuelReport, setFuelReport] = useState<any>(null);

  useEffect(() => {
    async function loadFuel() {
      const data = await fetchFromApi<any>("/fuel-context?location=Delhi", null);
      if (data) {
        setFuelReport(data);
      }
    }
    loadFuel();
  }, []);

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <SectionHeader
        title="Phoenix Aviation Turbine Fuel (ATF) Macro Overlay"
        headline="Explanatory macroeconomic overlay tracking state oil company jet fuel revisions alongside the headline airfare index."
        badge="PHOENIX MACRO INTELLIGENCE"
        badgeVariant="solid"
        action={
          <div className="flex items-center gap-2 font-mono text-xs text-ink bg-canvas px-3 py-1.5 rounded-[18px] border border-hairline">
            <Fuel className="h-4 w-4 text-ink" />
            <span className="font-medium">~38% OPERATING COST SHARE</span>
          </div>
        }
      />

      {/* Fuel Context Banner */}
      <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-mid-gray">
                JET FUEL BENCHMARK OVERVIEW
              </span>
              <PrototypePill />
            </div>

            <div className="flex items-baseline gap-4">
              <span className="text-5xl sm:text-6xl font-bold tracking-tight text-ink font-sans">
                ₹97,800
              </span>
              <div className="flex flex-col">
                <span className="rounded-[18px] bg-canvas text-ink border border-hairline px-2.5 py-1 text-xs font-mono font-medium">
                  +3.82% Monthly Revision
                </span>
                <span className="text-xs text-mid-gray font-mono mt-0.5">Per kilolitre (Delhi IOCL rate)</span>
              </div>
            </div>

            <p className="text-xs text-mid-gray leading-relaxed">
              Jet fuel is the single largest cost input for domestic airlines (~38% of Cost per Available Seat Kilometer). However, Phoenix Observatory presents ATF as an <strong className="text-ink">explanatory macroeconomic overlay</strong> rather than claiming a short-term direct causal link.
            </p>
          </div>

          <div className="rounded-nested border border-hairline bg-surface-alt p-4 font-mono text-xs space-y-2 lg:w-72 shrink-0">
            <div className="flex justify-between">
              <span className="text-mid-gray">Cost Share (CASM):</span>
              <strong className="text-ink">~35% to 45%</strong>
            </div>
            <div className="flex justify-between">
              <span className="text-mid-gray">Carrier Hedge Lag:</span>
              <strong className="text-ink">12 - 18 Months</strong>
            </div>
            <div className="flex justify-between border-t border-hairline pt-1.5">
              <span className="text-mid-gray">Statistical Claim:</span>
              <strong className="text-ink font-semibold">Non-Causal Overlay</strong>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Current ATF Benchmark"
          value="₹97,800 / kL"
          subtitle="Delhi IOCL domestic rate"
          accent="default"
          icon={Fuel}
        />
        <StatCard
          title="ATF 30-Day Movement"
          value="+3.82%"
          change={3.82}
          changeLabel="Recent fortnightly revision"
          accent="default"
          icon={TrendingUp}
        />
        <StatCard
          title="Airline Cost Sensitivity"
          value="~38%"
          subtitle="Operating CASM expenditure"
          accent="default"
          icon={DollarSign}
        />
        <StatCard
          title="Pass-Through Lag"
          value="12 - 18 Mo."
          subtitle="Hedging & forward contracts"
          accent="default"
          icon={Calendar}
        />
      </div>

      {/* Recharts Comparative Chart: ATF vs Airfare Index */}
      <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-ink font-sans">
              ATF Spot Price Revisions vs National Airfare Series
            </h2>
            <p className="text-xs text-mid-gray">
              Tracking normalized weekly movements of jet fuel against the T+15 headline price index.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-mid-gray">
              <span className="h-2 w-2 rounded-full bg-mid-gray" />
              <span>ATF Benchmark Index</span>
            </span>
            <span className="flex items-center gap-1.5 text-ink">
              <span className="h-2 w-2 rounded-full bg-ink" />
              <span>Airfare Headline Index</span>
            </span>
          </div>
        </div>

        <LineChart
          data={fuelSeries}
          xKey="date"
          height={280}
          series={[
            {
              key: "atfIndex",
              name: "ATF Benchmark (Rebased)",
              color: "#38bdf8",
              strokeWidth: 2,
            },
            {
              key: "fareIndex",
              name: "Airfare T+15 Index",
              color: "#f97316",
              strokeWidth: 2.5,
            },
          ]}
        />
      </div>

      {/* Comparative Table */}
      <div className="rounded-cards border border-hairline bg-paper shadow-subtle overflow-hidden">
        <div className="px-6 py-4 border-b border-hairline flex items-center justify-between">
          <span className="font-semibold text-sm text-ink font-sans">Weekly Price Revision Log</span>
          <span className="text-xs font-mono text-mid-gray">Base: 01 Aug 2026 = 100.0</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-hairline bg-surface-alt text-mid-gray uppercase tracking-wider text-[11px]">
                <th className="px-6 py-3.5 font-semibold">Date</th>
                <th className="px-6 py-3.5 font-semibold">ATF Price (₹ / kL)</th>
                <th className="px-6 py-3.5 font-semibold">ATF Rebased Index</th>
                <th className="px-6 py-3.5 font-semibold">Airfare T+15 Index</th>
                <th className="px-6 py-3.5 font-semibold text-right">Relationship Classification</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline/60 font-sans text-xs">
              {fuelSeries.map((row) => (
                <tr key={row.date} className="hover:bg-canvas transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-ink">{row.date}</td>
                  <td className="px-6 py-4 font-mono font-bold text-ink">₹{row.atf.toLocaleString()}</td>
                  <td className="px-6 py-4 font-mono font-bold text-mid-gray">{row.atfIndex.toFixed(1)}</td>
                  <td className="px-6 py-4 font-mono font-bold text-ink">{row.fareIndex.toFixed(1)}</td>
                  <td className="px-6 py-4 text-right">
                    <Badge variant="soft" size="xs">
                      CONTEXTUAL OVERLAY
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Real-World Critique Disclaimer Footnote */}
      <div className="rounded-cards border border-hairline bg-surface-alt p-5 flex items-start gap-3.5 text-xs text-mid-gray">
        <Info className="h-5 w-5 text-ink shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="font-bold text-ink text-xs uppercase font-mono tracking-wider">
            Statistical Integrity Note on Fuel Correlation
          </h4>
          <p className="leading-relaxed">
            <strong>Non-Causal Methodology Notice:</strong> Aviation Turbine Fuel constitutes approximately 38% of Indian airline operating expenses. However, APIX-2.0 presents ATF as a <strong>macroeconomic context overlay</strong> rather than asserting an unproven short-term 30-day causal pass-through. Indian carriers manage complex fuel hedges (12–18 month cycles) and utilize dynamic revenue management algorithms, meaning short-term fare fluctuations are primarily driven by booking horizon demand elasticity rather than day-to-day fuel spot price revisions.
          </p>
        </div>
      </div>
    </div>
  );
}
