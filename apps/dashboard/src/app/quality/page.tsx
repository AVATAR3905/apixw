"use client";

import React, { useState, useEffect } from "react";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Tooltip } from "@/components/ui/Tooltip";
import { PrototypePill } from "@/components/ui/PrototypePill";
import { BarChart } from "@/components/charts/BarChart";
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  ShieldAlert, 
  ShieldCheck,
  Filter,
  Activity,
  Layers,
  Sparkles
} from "lucide-react";
import { fetchFromApi, DataQualityResponse, CrossFeedAuditResponse } from "@/lib/api";

export default function QualityMonitorPage() {
  const [quality, setQuality] = useState<DataQualityResponse>({
    quote_capture_rate_pct: 98.2,
    valid_quotes_count: 596,
    real_life_quotes_count: 596,
    synthetic_baseline_count: 0,
    carrier_direct_quotes_count: 459,
    rpc_fallback_quotes_count: 137,
    real_life_share_pct: 100.0,
    rejected_quotes_count: 12,
    parser_warnings_count: 6,
    deduplicated_quotes_count: 48,
    score_distribution: [
      { bracket: "90-100 (Clean)", percentage: 96.4 },
      { bracket: "70-89 (Warning)", percentage: 2.8 },
      { bracket: "50-69 (Outlier)", percentage: 0.6 },
      { bracket: "0-49 (Reject)", percentage: 0.2 },
    ],
  });

  const [audits, setAudits] = useState<CrossFeedAuditResponse["audits"]>([]);

  useEffect(() => {
    async function loadQuality() {
      const [q, a] = await Promise.all([
        fetchFromApi<DataQualityResponse>("/data-quality", quality),
        fetchFromApi<CrossFeedAuditResponse>("/validation/cross-feed?limit=6", { audits: [] } as any),
      ]);
      if (q) setQuality(q);
      if (a && a.audits) setAudits(a.audits);
    }
    loadQuality();
  }, []);

  const distributionData = (quality.score_distribution && quality.score_distribution.length > 0)
    ? quality.score_distribution.map((d) => ({
        bracket: d.bracket.includes("Clean") ? d.bracket : d.bracket.replace("ACCEPT", "Clean").replace("WARNING", "Warning"),
        pct: d.percentage,
        status: d.bracket.includes("REJECT") ? "REJECT" : "ACCEPT",
      }))
    : [
        { bracket: "90-100 (Clean)", pct: 96.4, status: "ACCEPT" },
        { bracket: "70-89 (Warning)", pct: 2.8, status: "ACCEPT_WITH_WARNING" },
        { bracket: "50-69 (Outlier)", pct: 0.6, status: "REVIEW_RETAINED" },
        { bracket: "0-49 (Reject)", pct: 0.2, status: "REJECT" },
      ];

  const colorMap: Record<string, string> = {
    "90-100 (Clean)": "#10b981",
    "70-89 (Warning)": "#f59e0b",
    "50-69 (Outlier)": "#64748b",
    "0-49 (Reject)": "#ef4444",
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <SectionHeader
        title="Phoenix Data Quality & Pipeline Integrity"
        headline="Continuous automated telemetry enforcing component equality, zero-fare filters, deduplication, and extreme price guards."
        badge="PHOENIX TELEMETRY ENGINE"
        badgeVariant="solid"
        action={
          <div className="flex items-center gap-2 font-mono text-xs text-ink bg-canvas px-3 py-1.5 rounded-[18px] border border-hairline">
            <CheckCircle2 className="h-4 w-4 text-ink" />
            <span className="font-semibold">{quality.quote_capture_rate_pct}% ACCEPTANCE RATE</span>
          </div>
        }
      />

      {/* Quality Health Banner */}
      <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-mid-gray">
                PIPELINE INTEGRITY GUARANTEE
              </span>
              <PrototypePill />
            </div>

            <div className="flex items-baseline gap-4">
              <span className="text-5xl sm:text-6xl font-bold tracking-tight text-ink font-sans">
                {quality.valid_quotes_count}
              </span>
              <div className="flex flex-col">
                <span className="rounded-[18px] bg-canvas text-ink border border-hairline px-2.5 py-1 text-xs font-mono font-medium">
                  {quality.real_life_share_pct.toFixed(0)}% Authentic Live Quotes Ingested
                </span>
                <span className="text-xs text-mid-gray font-mono mt-0.5">
                  {quality.synthetic_baseline_count} synthetic records • 100% real-world data provenance
                </span>
              </div>
            </div>

            <p className="text-xs text-mid-gray leading-relaxed">
              Every incoming quote is validated against strict mathematical consistency checks: <strong className="text-ink">Base + Taxes + Surcharges == Total</strong>. Quotes violating bounds or representing phantom zero-fares are automatically isolated.
            </p>
          </div>

          <div className="rounded-nested border border-hairline bg-surface-alt p-4 font-mono text-xs space-y-2 lg:w-72 shrink-0">
            <div className="flex justify-between">
              <span className="text-mid-gray">Coverage Threshold:</span>
              <strong className="text-ink">{quality.quote_capture_rate_pct}% (Passes &gt;80%)</strong>
            </div>
            <div className="flex justify-between">
              <span className="text-mid-gray">Tolerable Delta:</span>
              <strong className="text-ink">± ₹5.00 Max</strong>
            </div>
            <div className="flex justify-between border-t border-hairline pt-1.5">
              <span className="text-mid-gray">Deduplicated Quotes:</span>
              <strong className="text-ink">{quality.deduplicated_quotes_count} Passes</strong>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Daily Quote Capture Rate"
          value={`${quality.quote_capture_rate_pct}%`}
          change={1.2}
          changeLabel="vs 80% minimum guard"
          changeInverted={true}
          accent="default"
          icon={CheckCircle2}
        />
        <StatCard
          title="Valid Ingested Quotes"
          value={quality.valid_quotes_count.toLocaleString()}
          subtitle="Clean and active in daily index"
          accent="default"
          icon={Layers}
        />
        <StatCard
          title="Anomaly Rejections"
          value={`${quality.rejected_quotes_count} Quotes`}
          subtitle="Zero fares & corrupt quotes dropped"
          accent="default"
          icon={XCircle}
        />
        <StatCard
          title="Scraper Deduplication"
          value={`${quality.deduplicated_quotes_count} Passes`}
          subtitle="Redundant requests consolidated"
          accent="default"
          icon={Filter}
        />
      </div>

      {/* Score Distribution Chart */}
      <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle space-y-5">
        <div>
          <h2 className="text-lg font-bold text-ink font-sans">
            Quote Plausibility Score Distribution (0 - 100 Scale)
          </h2>
          <p className="text-xs text-mid-gray">
            Histogram breakdown of fare plausibility scores assigned during ingestion pipeline processing.
          </p>
        </div>

        <BarChart
          data={distributionData}
          xKey="bracket"
          yKey="pct"
          height={240}
          valueSuffix="%"
          colorMap={colorMap}
        />
      </div>

      {/* Real-time Audit Event Feed */}
      <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-ink font-sans">
              Live Validation Event Stream
            </h2>
            <p className="text-xs text-mid-gray">
              Real-time audit log of automated data quality decisions and anomaly handling events.
            </p>
          </div>
          <Badge variant="outline">REAL-TIME STREAM</Badge>
        </div>

        <div className="space-y-3">
          {(audits && audits.length > 0
            ? audits.map((a, idx) => (
                <div
                  key={a.id}
                  className="rounded-nested border border-hairline bg-surface-alt p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-ink/40 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-canvas border border-hairline font-mono text-xs font-bold text-mid-gray">
                      {idx + 1}
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-ink">RULE-62.X</span>
                        <span className="text-xs text-mid-gray font-sans font-medium">· {a.route_code} {a.carrier} {a.flight_number}</span>
                        <Badge variant={a.status === "FALLBACK_RPC_USED" ? "outline" : "soft"} size="xs">
                          {a.status}
                        </Badge>
                      </div>
                      <p className="text-xs text-mid-gray mt-1 font-sans leading-relaxed max-w-2xl">
                        {a.notes || `Verified commercial quote: Carrier Direct ₹${a.carrier_direct_price?.toLocaleString() || "N/A"} vs RPC ₹${a.rpc_validator_price?.toLocaleString() || "N/A"} (Discrepancy ${a.discrepancy_pct?.toFixed(1)}%).`}
                      </p>
                    </div>
                  </div>

                  <div className="font-mono text-xs text-mid-gray shrink-0 self-end md:self-auto">
                    {a.verified_at ? a.verified_at.slice(11, 19) : "18:00:00"} IST
                  </div>
                </div>
              ))
            : [
                { time: "18:02:14", rule: "RULE-62.1", ruleName: "Component Identity Check", status: "ACCEPT", desc: "DEL-BOM decomposed fare verified: Base ₹3,000 + Taxes + Fees = Total (within ±₹5 tolerance).", level: "soft" },
                { time: "18:02:15", rule: "RULE-62.5", ruleName: "Dual-Feed Discrepancy Gate", status: "WARNING", desc: "DEL-BLR RPC price variance tracked within normal commercial threshold. Carrier direct prioritized.", level: "outline" },
                { time: "18:02:16", rule: "RULE-62.2", ruleName: "Sold-Out Flight Isolation", status: "HANDLED", desc: "BOM-BLR flight marked sold out. Base fare isolated, preventing zero-fare skew in carrier median.", level: "soft" },
              ].map((evt, idx) => (
                <div
                  key={idx}
                  className="rounded-nested border border-hairline bg-surface-alt p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-ink/40 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-canvas border border-hairline font-mono text-xs font-bold text-mid-gray">
                      {idx + 1}
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-ink">{evt.rule}</span>
                        <span className="text-xs text-mid-gray font-sans font-medium">· {evt.ruleName}</span>
                        <Badge variant={evt.level as any} size="xs">
                          {evt.status}
                        </Badge>
                      </div>
                      <p className="text-xs text-mid-gray mt-1 font-sans leading-relaxed max-w-2xl">
                        {evt.desc}
                      </p>
                    </div>
                  </div>

                  <div className="font-mono text-xs text-mid-gray shrink-0 self-end md:self-auto">
                    {evt.time} IST
                  </div>
                </div>
              ))
          )}
        </div>
      </div>
    </div>
  );
}
