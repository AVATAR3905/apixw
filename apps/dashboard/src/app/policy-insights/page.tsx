"use client";

import React, { useEffect, useState } from "react";
import {
  fetchFromApi,
  PolicySignalResponse,
  LeadingIndicatorResponse,
  AnomalyAlertsResponse,
  ConcentrationResponse,
  IntradayVolatilityResponse,
  AvailabilityAdjustedResponse,
  UdanResponse,
} from "@/lib/api";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatCard } from "@/components/ui/StatCard";
import { Badge } from "@/components/ui/Badge";
import type { BadgeVariant } from "@/components/ui/Badge";
import {
  Gavel,
  TrendingUp,
  Users,
  Clock,
  PlaneTakeoff,
  Landmark,
  AlertTriangle,
  Info,
} from "lucide-react";

function hhiBadgeVariant(band: string): BadgeVariant {
  if (band === "HIGH") return "danger";
  if (band === "MODERATE") return "warning";
  return "success";
}

function severityBadgeVariant(severity: string): BadgeVariant {
  if (severity === "SEVERE") return "danger";
  if (severity === "MODERATE") return "warning";
  return "neutral";
}

export default function PolicyInsightsPage() {
  const [policySignal, setPolicySignal] = useState<PolicySignalResponse | null>(null);
  const [leadingIndicator, setLeadingIndicator] = useState<LeadingIndicatorResponse | null>(null);
  const [alerts, setAlerts] = useState<AnomalyAlertsResponse | null>(null);
  const [concentration, setConcentration] = useState<ConcentrationResponse | null>(null);
  const [intraday, setIntraday] = useState<IntradayVolatilityResponse | null>(null);
  const [availability, setAvailability] = useState<AvailabilityAdjustedResponse | null>(null);
  const [udan, setUdan] = useState<UdanResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAll() {
      setLoading(true);
      const [ps, li, al, cc, iv, av, ud] = await Promise.all([
        fetchFromApi<PolicySignalResponse>("/analytics/policy-signal"),
        fetchFromApi<LeadingIndicatorResponse>("/analytics/leading-indicator"),
        fetchFromApi<AnomalyAlertsResponse>("/analytics/alerts"),
        fetchFromApi<ConcentrationResponse>("/analytics/concentration"),
        fetchFromApi<IntradayVolatilityResponse>("/analytics/intraday-volatility"),
        fetchFromApi<AvailabilityAdjustedResponse>("/analytics/availability-adjusted"),
        fetchFromApi<UdanResponse>("/analytics/udan"),
      ]);
      setPolicySignal(ps);
      setLeadingIndicator(li);
      setAlerts(al);
      setConcentration(cc);
      setIntraday(iv);
      setAvailability(av);
      setUdan(ud);
      setLoading(false);
    }
    loadAll();
  }, []);

  return (
    <div className="space-y-8">
      <SectionHeader
        title="Policy & Regulatory Insights"
        headline="Rules-based early-warning signals for MoSPI/RBI price-transmission review, CCI market-concentration monitoring, and MoCA UDAN affordability oversight — computed directly from the observatory's own quote data, not editorialized."
        badge="POLICY SIGNALS"
        badgeVariant="solid"
      />

      {/* Top-line KPI row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Fare Elevation Classification"
          value={policySignal?.classification || "—"}
          subtitle={
            policySignal
              ? `${policySignal.evidence.elevation_pct.toFixed(1)}% above baseline${policySignal.classification === "STRUCTURAL" ? " — passthrough review" : ""}`
              : "Awaiting data"
          }
          icon={<Gavel className="h-6 w-6" />}
        />
        <StatCard
          title="CPI Leading-Indicator Alignment"
          value={leadingIndicator ? `${leadingIndicator.aligned_weeks}/${leadingIndicator.required_aligned_weeks} weeks` : "—"}
          subtitle={leadingIndicator?.status === "COMPLETED" ? `Best lag: ${leadingIndicator.best_lag_weeks ?? "n/a"} wk` : "Insufficient real overlap with MoSPI release calendar"}
          icon={<TrendingUp className="h-6 w-6" />}
          badge={leadingIndicator?.status === "COMPLETED" ? "Computed" : "Gated"}
          badgeVariant={leadingIndicator?.status === "COMPLETED" ? "success" : "neutral"}
        />
        <StatCard
          title="Network Avg HHI"
          value={concentration ? concentration.network_avg_hhi.toFixed(0) : "—"}
          subtitle={concentration ? `${concentration.high_concentration_routes.length} of ${concentration.monitored_route_count} routes HIGH concentration` : "Awaiting data"}
          icon={<Users className="h-6 w-6" />}
          badge={concentration && concentration.high_concentration_routes.length > 0 ? "CCI Watch" : "Competitive"}
          badgeVariant={concentration && concentration.high_concentration_routes.length > 0 ? "danger" : "success"}
        />
        <StatCard
          title="UDAN Affordability Breaches"
          value={udan ? `${udan.breach_count} routes` : "—"}
          subtitle={udan ? `Trunk median ₹${udan.trunk_median_fare.toLocaleString("en-IN")} vs ₹${udan.udan_target_inr.toLocaleString("en-IN")} target` : "Awaiting data"}
          icon={<Landmark className="h-6 w-6" />}
          badge={udan && udan.breach_count > 0 ? "Subsidy Review" : "Within Target"}
          badgeVariant={udan && udan.breach_count > 0 ? "warning" : "success"}
        />
      </div>

      {/* Policy Signal detail */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline">
          <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
            <Gavel className="h-4 w-4 text-ink" />
            Fare Elevation Classification (RBI MPC Framing)
          </h3>
          <p className="text-xs text-mid-gray font-sans mt-0.5">
            Rules-based decomposition of persistence, carrier breadth, calendar correlation, and ATF co-movement.
          </p>
        </div>
        <div className="p-6 space-y-4">
          {policySignal ? (
            <>
              <p className="text-sm text-ink font-sans leading-relaxed border-l-2 border-ink pl-4">
                {policySignal.policy_line}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-sans">
                <div>
                  <div className="text-mid-gray uppercase tracking-wide text-[10px] mb-1">Persistence</div>
                  <div className="font-mono font-semibold text-ink">{policySignal.evidence.persistence_days} day(s)</div>
                </div>
                <div>
                  <div className="text-mid-gray uppercase tracking-wide text-[10px] mb-1">Carrier Breadth</div>
                  <div className="font-mono font-semibold text-ink">{policySignal.evidence.carrier_breadth} carriers</div>
                </div>
                <div>
                  <div className="text-mid-gray uppercase tracking-wide text-[10px] mb-1">ATF Co-movement</div>
                  <div className="font-mono font-semibold text-ink">
                    {policySignal.evidence.atf_move_pct != null ? `${policySignal.evidence.atf_move_pct.toFixed(1)}%` : "n/a"}
                    {policySignal.evidence.atf_aligned && <span className="text-emerald-600"> (aligned)</span>}
                  </div>
                </div>
                <div>
                  <div className="text-mid-gray uppercase tracking-wide text-[10px] mb-1">Structural vs Transient Score</div>
                  <div className="font-mono font-semibold text-ink">
                    {policySignal.evidence.structural_score} / {policySignal.evidence.transient_score}
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-mid-gray font-sans italic pt-2 border-t border-hairline">{policySignal.disclosure}</p>
            </>
          ) : (
            <p className="text-sm text-mid-gray font-sans">Awaiting data.</p>
          )}
        </div>
      </div>

      {/* Leading indicator */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline">
          <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
            <TrendingUp className="h-4 w-4 text-ink" />
            Billion-Prices Leading Indicator vs Official CPI
          </h3>
          <p className="text-xs text-mid-gray font-sans mt-0.5">
            IMF/Harvard PriceStats-style lead-lag correlation against {leadingIndicator?.benchmark_indicator || "the MoSPI benchmark"}.
          </p>
        </div>
        <div className="p-6 space-y-3">
          {leadingIndicator ? (
            leadingIndicator.status === "COMPLETED" ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-sans">
                  <thead>
                    <tr className="border-b border-hairline uppercase tracking-[0.6px] text-mid-gray text-[11px]">
                      <th className="py-2 pr-4">Lag (weeks)</th>
                      <th className="py-2 pr-4">Correlation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline">
                    {leadingIndicator.lags.map((l) => (
                      <tr key={l.lag_weeks}>
                        <td className="py-2 pr-4 font-mono text-ink">{l.lag_weeks}</td>
                        <td className="py-2 pr-4 font-mono text-ink">{l.correlation.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex items-start gap-3 rounded-nested border border-hairline bg-canvas p-4">
                <Info className="h-4 w-4 text-mid-gray shrink-0 mt-0.5" />
                <p className="text-xs text-mid-gray font-sans">
                  <span className="font-semibold text-ink">Insufficient alignment: </span>
                  only {leadingIndicator.aligned_weeks} of {leadingIndicator.required_aligned_weeks} required calendar
                  weeks currently overlap between this prototype&apos;s operating history and the MoSPI benchmark&apos;s
                  release calendar. Reported honestly as gated rather than computing a correlation from too few points.
                </p>
              </div>
            )
          ) : (
            <p className="text-sm text-mid-gray font-sans">Awaiting data.</p>
          )}
          {leadingIndicator && (
            <p className="text-[11px] text-mid-gray font-sans italic pt-2 border-t border-hairline">
              {leadingIndicator.methodology_disclosure}
            </p>
          )}
        </div>
      </div>

      {/* Anomaly alerts */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
              <AlertTriangle className="h-4 w-4 text-ink" />
              Explainable Anomaly Alerts
            </h3>
            <p className="text-xs text-mid-gray font-sans mt-0.5">
              {alerts ? `${alerts.total_alerts} alerts, ${alerts.unexplained_count} unexplained` : "Awaiting data"}
            </p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas font-sans uppercase tracking-[0.6px] text-mid-gray text-[11px] font-medium">
                <th className="px-6 py-3.5">Date</th>
                <th className="px-6 py-3.5">Severity</th>
                <th className="px-6 py-3.5">Z-Score</th>
                <th className="px-6 py-3.5">Detected vs Median</th>
                <th className="px-6 py-3.5">Explanation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {alerts?.alerts.map((a) => (
                <tr key={a.id} className="hover:bg-canvas transition-colors">
                  <td className="px-6 py-4 font-mono text-ink">{a.observation_date}</td>
                  <td className="px-6 py-4">
                    <Badge variant={severityBadgeVariant(a.severity)} size="sm">{a.severity}</Badge>
                  </td>
                  <td className="px-6 py-4 font-mono text-ink">{a.z_score.toFixed(2)}</td>
                  <td className="px-6 py-4 font-mono text-ink">
                    {a.detected_value.toFixed(2)} vs {a.reference_median.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 text-mid-gray max-w-md">{a.explanation?.plain_text || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Concentration / HHI */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline">
          <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
            <Users className="h-4 w-4 text-ink" />
            Carrier Concentration (HHI) — CCI Monitoring
          </h3>
          <p className="text-xs text-mid-gray font-sans mt-0.5">
            {concentration
              ? `Correlation HHI↔fare ${concentration.correlation_hhi_vs_fare?.toFixed(3) ?? "n/a"} · HHI↔volatility ${concentration.correlation_hhi_vs_volatility?.toFixed(3) ?? "n/a"}`
              : "Awaiting data"}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas font-sans uppercase tracking-[0.6px] text-mid-gray text-[11px] font-medium">
                <th className="px-6 py-3.5">Corridor</th>
                <th className="px-6 py-3.5">Type</th>
                <th className="px-6 py-3.5">HHI</th>
                <th className="px-6 py-3.5">Band</th>
                <th className="px-6 py-3.5">Carriers</th>
                <th className="px-6 py-3.5">Mean Fare</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {concentration?.routes.map((r) => (
                <tr key={r.route_code} className="hover:bg-canvas transition-colors">
                  <td className="px-6 py-4 font-mono font-semibold text-ink">
                    {r.route_code}
                    <span className="text-[11px] font-sans font-normal text-mid-gray ml-2">
                      ({r.origin} &rarr; {r.destination})
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={r.corridor_type === "METRO_TRUNK" ? "secondary" : "outline"} size="sm">
                      {r.corridor_type === "METRO_TRUNK" ? "Trunk" : "Regional"}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 font-mono text-ink">{r.hhi.toFixed(0)}</td>
                  <td className="px-6 py-4">
                    <Badge variant={hhiBadgeVariant(r.hhi_band)} size="sm">{r.hhi_band}</Badge>
                  </td>
                  <td className="px-6 py-4 font-mono text-mid-gray">
                    {r.carriers.map((c) => c.carrier_code).join(", ")}
                  </td>
                  <td className="px-6 py-4 font-mono text-ink">&#8377;{r.mean_fare.toLocaleString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {concentration && (
          <p className="px-6 py-4 text-[11px] text-mid-gray font-sans italic border-t border-hairline">
            {concentration.cci_relevance}
          </p>
        )}
      </div>

      {/* Intraday volatility */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline">
          <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
            <Clock className="h-4 w-4 text-ink" />
            Intraday Pricing Volatility &amp; Best-Time-To-Book
          </h3>
          <p className="text-xs text-mid-gray font-sans mt-0.5">
            {intraday ? `Network average CV: ${intraday.network_avg_intraday_volatility_pct.toFixed(1)}%` : "Awaiting data"}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas font-sans uppercase tracking-[0.6px] text-mid-gray text-[11px] font-medium">
                <th className="px-6 py-3.5">Corridor</th>
                <th className="px-6 py-3.5">Intraday CV</th>
                <th className="px-6 py-3.5">Windows</th>
                <th className="px-6 py-3.5">Best Time To Book</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {intraday?.routes.map((r) => (
                <tr key={r.route_code} className="hover:bg-canvas transition-colors">
                  <td className="px-6 py-4 font-mono font-semibold text-ink">
                    {r.route_code}
                    <span className="text-[11px] font-sans font-normal text-mid-gray ml-2">
                      ({r.origin} &rarr; {r.destination})
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-ink">{r.intraday_volatility_pct.toFixed(1)}%</td>
                  <td className="px-6 py-4 font-mono text-mid-gray">{r.windows_observed}</td>
                  <td className="px-6 py-4 font-mono text-ink">
                    {r.best_time_to_book
                      ? `${r.best_time_to_book.window.replace(/_/g, " ")} (₹${r.best_time_to_book.mean_fare.toLocaleString("en-IN")})`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {intraday && (
          <p className="px-6 py-4 text-[11px] text-mid-gray font-sans italic border-t border-hairline">
            {intraday.interpretation}
          </p>
        )}
      </div>

      {/* Availability-adjusted index */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline">
          <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
            <PlaneTakeoff className="h-4 w-4 text-ink" />
            Availability-Adjusted Index
          </h3>
          <p className="text-xs text-mid-gray font-sans mt-0.5">
            {availability
              ? `Network scarcity premium: ${availability.network_scarcity_premium_pct.toFixed(1)}% (sold-out ratio ${(availability.network_sold_out_ratio * 100).toFixed(1)}%)`
              : "Awaiting data"}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas font-sans uppercase tracking-[0.6px] text-mid-gray text-[11px] font-medium">
                <th className="px-6 py-3.5">Corridor</th>
                <th className="px-6 py-3.5">Headline Fare</th>
                <th className="px-6 py-3.5">Sold-Out Ratio</th>
                <th className="px-6 py-3.5">Scarcity Premium</th>
                <th className="px-6 py-3.5">Adjusted Fare</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {availability?.routes.map((r) => (
                <tr key={r.route_code} className="hover:bg-canvas transition-colors">
                  <td className="px-6 py-4 font-mono font-semibold text-ink">
                    {r.route_code}
                    <span className="text-[11px] font-sans font-normal text-mid-gray ml-2">
                      ({r.origin} &rarr; {r.destination})
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-ink">&#8377;{r.headline_fare.toLocaleString("en-IN")}</td>
                  <td className="px-6 py-4 font-mono text-mid-gray">{(r.sold_out_ratio * 100).toFixed(1)}%</td>
                  <td className="px-6 py-4 font-mono text-ink">{r.scarcity_premium_pct.toFixed(1)}%</td>
                  <td className="px-6 py-4 font-mono text-ink">&#8377;{r.availability_adjusted_fare.toLocaleString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {availability && (
          <p className="px-6 py-4 text-[11px] text-mid-gray font-sans italic border-t border-hairline">
            {availability.methodology_disclosure}
          </p>
        )}
      </div>

      {/* UDAN affordability monitor */}
      <div className="rounded-cards border border-hairline bg-paper overflow-hidden shadow-subtle">
        <div className="p-6 border-b border-hairline">
          <h3 className="text-base font-semibold text-ink flex items-center gap-2 font-sans">
            <Landmark className="h-4 w-4 text-ink" />
            UDAN Regional Affordability Monitor
          </h3>
          <p className="text-xs text-mid-gray font-sans mt-0.5">
            {udan ? `UDAN target ₹${udan.udan_target_inr.toLocaleString("en-IN")} · trunk median ₹${udan.trunk_median_fare.toLocaleString("en-IN")}` : "Awaiting data"}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas font-sans uppercase tracking-[0.6px] text-mid-gray text-[11px] font-medium">
                <th className="px-6 py-3.5">Regional Route</th>
                <th className="px-6 py-3.5">Latest Fare</th>
                <th className="px-6 py-3.5">vs UDAN Target</th>
                <th className="px-6 py-3.5">vs Trunk Median</th>
                <th className="px-6 py-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {udan?.routes.map((r) => (
                <tr key={r.route_code} className="hover:bg-canvas transition-colors">
                  <td className="px-6 py-4 font-mono font-semibold text-ink">
                    {r.route_code}
                    <span className="text-[11px] font-sans font-normal text-mid-gray ml-2">
                      ({r.origin} &rarr; {r.destination})
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-ink">&#8377;{r.latest_fare.toLocaleString("en-IN")}</td>
                  <td className="px-6 py-4 font-mono text-ink">{r.ratio_vs_udan_target.toFixed(2)}&times;</td>
                  <td className="px-6 py-4 font-mono text-mid-gray">{r.ratio_vs_trunk.toFixed(2)}&times;</td>
                  <td className="px-6 py-4">
                    <Badge variant={r.status === "BREACH" ? "danger" : "success"} size="sm">{r.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {udan && (
          <p className="px-6 py-4 text-[11px] text-mid-gray font-sans italic border-t border-hairline">
            {udan.policy_note}
          </p>
        )}
      </div>

      {!loading && !policySignal && !concentration && (
        <div className="rounded-nested border border-hairline bg-canvas p-6 text-center text-sm text-mid-gray font-sans">
          Unable to reach the analytics API. Check that the FastAPI backend is running.
        </div>
      )}
    </div>
  );
}
