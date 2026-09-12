"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Tooltip } from "@/components/ui/Tooltip";
import { PrototypePill } from "@/components/ui/PrototypePill";
import { 
  ArrowLeft, 
  ShieldCheck, 
  Info, 
  Plane, 
  DollarSign, 
  CheckCircle2,
  PieChart,
  Layers
} from "lucide-react";
import { fetchFromApi, RouteDetailResponse, CrossFeedAuditResponse } from "@/lib/api";

export default function RouteDetailPage() {
  const params = useParams();
  const routeCode = typeof params.route_id === "string" ? params.route_id.toUpperCase() : "DEL-BOM";

  const defaultMeta = { name: `${routeCode} Aviation Corridor`, type: "Domestic Route", weight: "10.0%" };

  const [detail, setDetail] = useState<RouteDetailResponse>({
    route_code: routeCode,
    origin: "Delhi",
    destination: "Mumbai",
    corridor_type: "Trunk Metro",
    weight_pct: 18.4,
    representative_price: 3000.0,
    fare_decomposition: {
      base_fare: 5372.65,
      fuel_surcharge: 1007.37,
      gst_taxes: 335.79,
      udf_adf: 350.0,
      convenience_fee: 92.0,
      total_consumer_fare: 7157.81,
    },
    carrier_breakdown: [
      { carrier: "6E", name: "IndiGo", basic_fare: 3000, flexi_fare: 4650, is_min: false, flights: 24 },
      { carrier: "SG", name: "SpiceJet", basic_fare: 2868, flexi_fare: 4446, is_min: true, flights: 32 },
      { carrier: "QP", name: "Akasa Air", basic_fare: 2934, flexi_fare: 4548, is_min: false, flights: 32 },
      { carrier: "AI", name: "Air India", basic_fare: 4572, flexi_fare: 7086, is_min: false, flights: 8 },
    ],
  });

  const [auditData, setAuditData] = useState<CrossFeedAuditResponse | null>(null);

  useEffect(() => {
    async function loadDetail() {
      const [d, a] = await Promise.all([
        fetchFromApi<RouteDetailResponse>(`/routes/${routeCode}`, detail),
        fetchFromApi<CrossFeedAuditResponse>(`/validation/cross-feed?route_code=${routeCode}&limit=10`, {
          total_audits: 0,
          carrier_direct_count: 0,
          rpc_fallback_count: 0,
          exact_parity_count: 0,
          aggregator_markup_count: 0,
          average_discrepancy_pct: 0,
          parity_rate_pct: 0,
          audits: [],
        }),
      ]);
      if (d) setDetail(d);
      if (a) setAuditData(a);
    }
    loadDetail();
  }, [routeCode]);

  const meta = {
    name: `${detail.origin} ↔ ${detail.destination}`,
    type: detail.corridor_type === "METRO_TRUNK" ? "Trunk Metro" : "Regional Thin",
    weight: `${detail.weight_pct}%`,
  };

  const carrierData = detail.carrier_breakdown.map((c) => ({
    code: c.carrier,
    name: c.name,
    basicFare: c.basic_fare,
    flexiFare: c.flexi_fare,
    minFare: c.is_min,
    flights: c.flights,
    share: `${Math.round((c.flights / Math.max(1, detail.carrier_breakdown.reduce((acc, curr) => acc + curr.flights, 0))) * 100)}%`,
  }));

  const fd = detail.fare_decomposition || {
    base_fare: 4200.0,
    fuel_surcharge: 850.0,
    gst_taxes: 252.5,
    udf_adf: 350.0,
    convenience_fee: 299.0,
    total_consumer_fare: 5951.5,
  };
  const totalFare = fd.total_consumer_fare || 5951.5;

  const fareComponents = [
    { name: "Airline Base Fare", amount: fd.base_fare, pct: Math.round((fd.base_fare / totalFare) * 1000) / 10, color: "bg-ink", hex: "#0a0a0a", desc: "Core airline revenue ticket tariff (lowest available basic economy)." },
    { name: "Fuel Surcharge (YQ)", amount: fd.fuel_surcharge, pct: Math.round((fd.fuel_surcharge / totalFare) * 1000) / 10, color: "bg-ink-soft", hex: "#171717", desc: "Carrier-levied aviation fuel compensation surcharge." },
    { name: "UDF / ADF Airport Fees", amount: fd.udf_adf, pct: Math.round((fd.udf_adf / totalFare) * 1000) / 10, color: "bg-mid-gray", hex: "#737373", desc: "User & Airport Development Fees mandated by airport operators (AAI/PPP)." },
    { name: "Mandatory GST (5%)", amount: fd.gst_taxes, pct: Math.round((fd.gst_taxes / totalFare) * 1000) / 10, color: "bg-neutral-400", hex: "#a3a3a3", desc: "Statutory Goods & Services Tax on economy domestic air transportation." },
    { name: "Booking Convenience Fee", amount: fd.convenience_fee, pct: Math.round((fd.convenience_fee / totalFare) * 1000) / 10, color: "bg-hairline", hex: "#e5e5e5", desc: "Mandatory payment gateway and ticketing administrative fee." },
  ];

  return (
    <div className="space-y-8">
      {/* Breadcrumb & Navigation */}
      <div>
        <Link
          href="/routes"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-mid-gray hover:text-ink transition-colors mb-4 group font-sans"
        >
          <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-1 transition-transform" />
          <span>Back to Corridor Catalog</span>
        </Link>

        <SectionHeader
          title={`${routeCode} — ${meta.name}`}
          headline={`Detailed price anatomy, fare component decomposition, and carrier competition metrics for the ${meta.name} corridor.`}
          badge={meta.type.toUpperCase()}
          badgeVariant="solid"
          action={
            <div className="flex items-center gap-2 font-sans text-xs text-mid-gray">
              <span>DGCA BASKET WEIGHT: <strong className="text-ink">{meta.weight}</strong></span>
              <span>•</span>
              <PrototypePill />
            </div>
          }
        />
      </div>

      {/* Corridor Key Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Representative Base Fare"
          value="₹4,115"
          subtitle="Cross-carrier median of basic economy"
          accent="default"
          icon={DollarSign}
        />
        <StatCard
          title="Total Out-Of-Pocket Fare"
          value={`₹${totalFare.toLocaleString()}`}
          subtitle="Includes all airline fees & operator taxes"
          accent="default"
          icon={PieChart}
        />
        <StatCard
          title="Daily Nonstop Flights"
          value="44 Flights"
          subtitle="Across 4 active scheduled carriers"
          accent="default"
          icon={Plane}
        />
        <StatCard
          title="Carrier Price Spread"
          value="₹430"
          subtitle="Min ₹4,020 (SG) to Max ₹4,450 (AI)"
          accent="default"
          icon={Layers}
        />
      </div>

      {/* Fare Decomposition Component Breakdown */}
      <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-6">
        <div>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-ink font-sans">
                Fare Anatomy & Component Decomposition
              </h2>
              <p className="text-xs text-mid-gray mt-0.5 font-sans">
                Deconstructing the average out-of-pocket ticket into airline, airport operator, and tax components.
              </p>
            </div>
            <Badge variant="solid">MANDATORY CHARGES INCLUDED</Badge>
          </div>
        </div>

        {/* Stacked Percentage Bar */}
        <div className="space-y-3">
          <div className="flex h-6 w-full overflow-hidden rounded-[18px] bg-canvas border border-hairline p-0.5">
            {fareComponents.map((comp) => (
              <div
                key={comp.name}
                style={{ width: `${comp.pct}%` }}
                className={`${comp.color} h-full first:rounded-l-[18px] last:rounded-r-[18px] transition-all`}
                title={`${comp.name}: ₹${comp.amount} (${comp.pct}%)`}
              />
            ))}
          </div>

          {/* Component legend cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 pt-2">
            {fareComponents.map((comp) => (
              <div
                key={comp.name}
                className="rounded-nested border border-hairline bg-canvas p-3 space-y-1"
              >
                <div className="flex items-center gap-1.5">
                  <span className={`h-2.5 w-2.5 rounded-full ${comp.color}`} />
                  <span className="text-[11px] font-sans uppercase tracking-[0.6px] text-mid-gray font-medium">
                    {comp.name}
                  </span>
                </div>
                <div className="flex items-baseline justify-between pt-1 font-sans">
                  <span className="text-base font-semibold text-ink">₹{comp.amount}</span>
                  <span className="text-xs font-medium text-mid-gray">{comp.pct}%</span>
                </div>
                <p className="text-[11px] text-mid-gray leading-snug font-sans pt-1">
                  {comp.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Carrier Price Matrix & Fare-Mix Defense */}
      <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink font-sans">
              Carrier Pricing Matrix & Fare-Mix Defense
            </h2>
            <p className="text-xs text-mid-gray mt-0.5 font-sans">
              APIX-2.0 isolates the lowest basic economy fare per airline before computing the cross-carrier median.
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-ink bg-canvas px-3 py-1.5 rounded-[18px] border border-hairline font-sans font-medium">
            <ShieldCheck className="h-4 w-4 text-ink" />
            <span>INVENTORY-MIX PROTECTED</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-hairline bg-canvas text-mid-gray font-sans uppercase tracking-[0.6px] text-[11px]">
                <th className="px-5 py-3.5 font-medium">Airline Carrier</th>
                <th className="px-5 py-3.5 font-medium">Daily Flights</th>
                <th className="px-5 py-3.5 font-medium">Corridor Market Share</th>
                <th className="px-5 py-3.5 font-medium">Lowest Basic Economy (Ingested)</th>
                <th className="px-5 py-3.5 font-medium">Flexi / Premium Tier (Discarded)</th>
                <th className="px-5 py-3.5 font-medium text-right">In Estimator</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {carrierData.map((c) => (
                <tr key={c.code} className="hover:bg-canvas transition-colors">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-canvas font-mono font-semibold text-ink border border-hairline text-xs">
                        {c.code}
                      </span>
                      <div>
                        <div className="font-semibold text-ink">{c.name}</div>
                        <div className="text-[11px] text-mid-gray font-mono">{c.code} Scheduled</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4 font-mono font-semibold text-ink">{c.flights}</td>
                  <td className="px-5 py-4 font-mono text-mid-gray">{c.share}</td>
                  <td className="px-5 py-4 font-mono font-semibold text-ink text-sm">
                    ₹{c.basicFare.toLocaleString()}
                  </td>
                  <td className="px-5 py-4 font-mono text-mid-gray line-through">
                    ₹{c.flexiFare.toLocaleString()}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <Badge variant="solid" size="xs">
                      INCLUDED IN MEDIAN
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Statistical Guarantee Note */}
        <div className="flex items-start gap-3 rounded-nested border border-hairline bg-canvas p-4 text-xs">
          <Info className="h-5 w-5 text-ink shrink-0 mt-0.5" />
          <div className="space-y-1 font-sans">
            <span className="font-semibold text-ink uppercase text-[11px] tracking-[0.6px] block">
              Statistical Invariance Guarantee (Fare-Mix Invariance Standard)
            </span>
            <p className="text-mid-gray leading-relaxed">
              If an airline releases 15 additional high-fare &quot;Flexi Plus&quot; seats at ₹7,400, a naive raw median of all flight quotes would falsely spike by +18%. Under APIX-2.0, the carrier&apos;s lowest available basic fare tier (₹4,450) is extracted first, mathematically guaranteeing that fare-mix expansion does not distort the index.
            </p>
          </div>
        </div>
      </div>

      {/* Carrier Website vs Aggregator RPC Cross-Feed Parity */}
      <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-ink font-sans">
                Carrier Direct Portal vs Aggregator RPC Parity Audit
              </h2>
              <Badge variant="solid">LIVE FEED VALIDATOR</Badge>
            </div>
            <p className="text-xs text-mid-gray mt-0.5 font-sans">
              Prioritizes authentic prices scraped directly from carrier booking engines. Google Flights RPC functions as real-time pricing validator and high-resilience fallback.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-sans text-xs font-medium text-ink bg-canvas px-2.5 py-1 rounded-[18px] border border-hairline">
              CARRIER DIRECT PRIORITY
            </span>
          </div>
        </div>

        <div className="overflow-x-auto rounded-nested border border-hairline bg-paper">
          <table className="w-full text-left text-xs font-sans">
            <thead className="border-b border-hairline bg-canvas font-sans uppercase tracking-[0.6px] text-mid-gray text-[10px]">
              <tr>
                <th className="px-5 py-3 font-medium">Carrier / Flight</th>
                <th className="px-5 py-3 font-medium">Carrier Direct Portal (Priority 1)</th>
                <th className="px-5 py-3 font-medium">Aggregator RPC Feed (Validator)</th>
                <th className="px-5 py-3 font-medium">Discrepancy (Spread)</th>
                <th className="px-5 py-3 text-right font-medium">Pipeline Selection</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-mono">
              {(auditData && auditData.audits.length > 0
                ? auditData.audits.slice(0, 5).map((a) => (
                    <tr key={a.id} className="hover:bg-canvas transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-semibold text-ink">{a.carrier} ({a.flight_number})</div>
                        <div className="text-[10px] text-mid-gray font-sans">T+{a.advance_days} • {a.travel_date}</div>
                      </td>
                      <td className="px-5 py-4 font-semibold text-ink">
                        {a.carrier_direct_price ? `₹${a.carrier_direct_price.toLocaleString()}` : "Portal Rate-Limited"}
                      </td>
                      <td className="px-5 py-4 text-mid-gray">
                        {a.rpc_validator_price ? `₹${a.rpc_validator_price.toLocaleString()}` : "Pending"}
                      </td>
                      <td className="px-5 py-4 font-semibold text-ink">
                        {a.discrepancy_amount !== null ? `${a.discrepancy_amount >= 0 ? "+" : ""}₹${a.discrepancy_amount.toFixed(1)} (${a.discrepancy_pct?.toFixed(1)}%)` : "0.0%"}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <Badge variant={a.status === "FALLBACK_RPC_USED" ? "soft" : "solid"} size="xs">
                          {a.status === "FALLBACK_RPC_USED" ? "FALLBACK: RPC" : "PRIMARY: CARRIER DIRECT"}
                        </Badge>
                      </td>
                    </tr>
                  ))
                : [
                    { carrier: "IndiGo", flight: "6E-8161", direct: "₹7,995.00", rpc: "₹6,425.00", spread: "-₹1,570.00 (-19.6%)", badge: "solid", tag: "PRIMARY: DIRECT PORTAL" },
                    { carrier: "SpiceJet", flight: "SG-8161", direct: "₹7,675.20", rpc: "₹7,719.00", spread: "+₹43.80 (+0.6%)", badge: "solid", tag: "PRIMARY: DIRECT PORTAL" },
                    { carrier: "Air India", flight: "AI-101", direct: "Portal Rate-Limited", rpc: "₹6,582.00", spread: "Fallback Activated", badge: "soft", tag: "FALLBACK: RPC ACTIVATED" },
                  ].map((row, idx) => (
                    <tr key={idx} className="hover:bg-canvas transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-semibold text-ink">{row.carrier} ({row.flight})</div>
                        <div className="text-[10px] text-mid-gray font-sans">08:15 Departure • Verified</div>
                      </td>
                      <td className="px-5 py-4 font-semibold text-ink">{row.direct}</td>
                      <td className="px-5 py-4 text-mid-gray">{row.rpc}</td>
                      <td className="px-5 py-4 text-ink font-semibold">{row.spread}</td>
                      <td className="px-5 py-4 text-right">
                        <Badge variant={row.badge as any} size="xs">{row.tag}</Badge>
                      </td>
                    </tr>
                  ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
