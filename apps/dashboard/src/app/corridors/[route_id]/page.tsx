"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { 
  ArrowLeft, 
  ShieldCheck, 
  Plane, 
  DollarSign, 
  CheckCircle2,
  PieChart,
  Layers,
  Fuel,
  Building,
  Receipt,
  Scale,
  Sparkles,
  ArrowUpDown,
  Tag,
  Clock
} from "lucide-react";
import { 
  fetchFromApi, 
  RouteDetailResponse, 
  CrossFeedAuditResponse,
  OTACommonFlightsResponse,
  OTACommonFlight
} from "@/lib/api";

export default function CorridorDetailPage() {
  const params = useParams();
  const routeCode = typeof params.route_id === "string" ? params.route_id.toUpperCase() : "DEL-BOM";

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

  const [otaHorizon, setOtaHorizon] = useState<number>(15);
  const [otaFlights, setOtaFlights] = useState<OTACommonFlight[]>([
    {
      flight_number: "6E-205",
      carrier_code: "6E",
      carrier_name: "IndiGo",
      origin_airport: "DEL",
      destination_airport: "BOM",
      travel_date: "2026-09-18",
      departure_time: "06:00",
      arrival_time: "08:15",
      canonical_median_fare: 4239.0,
      min_walkaway_fare: 3540.0,
      max_observed_fare: 4523.5,
      carrier_direct_fare: 3540.0,
      spread_inr: 983.5,
      spread_pct: 23.2,
      cheapest_source: "Carrier Direct (IndiGo)",
      sources_count: 7,
      platform_matrix: {
        "Carrier Direct": { source_name: "Carrier Direct", source_domain: "goindigo.in", base_fare: 3000, taxes_and_fees: 540, convenience_fee: 0, promotional_discount: 0, total_fare: 3540, is_cheapest: true, markup_vs_direct: 0 },
        "EaseMyTrip": { source_name: "EaseMyTrip", source_domain: "easemytrip.com", base_fare: 3000, taxes_and_fees: 540, convenience_fee: 0, promotional_discount: 0, total_fare: 3540, is_cheapest: true, markup_vs_direct: 0 },
        "Skyscanner": { source_name: "Skyscanner India", source_domain: "skyscanner.co.in", base_fare: 3000, taxes_and_fees: 540, convenience_fee: 0, promotional_discount: 0, total_fare: 3590, is_cheapest: false, markup_vs_direct: 50 },
        "Cleartrip": { source_name: "Cleartrip", source_domain: "cleartrip.com", base_fare: 3000, taxes_and_fees: 540, convenience_fee: 349, promotional_discount: 150, total_fare: 3739, is_cheapest: false, markup_vs_direct: 199 },
        "Ixigo": { source_name: "Ixigo Flights", source_domain: "ixigo.com", base_fare: 3000, taxes_and_fees: 540, convenience_fee: 360, promotional_discount: 120, total_fare: 3780, is_cheapest: false, markup_vs_direct: 240 },
        "MakeMyTrip": { source_name: "MakeMyTrip India", source_domain: "makemytrip.com", base_fare: 3000, taxes_and_fees: 540, convenience_fee: 420, promotional_discount: 150, total_fare: 3810, is_cheapest: false, markup_vs_direct: 270 },
        "Yatra": { source_name: "Yatra Online", source_domain: "yatra.com", base_fare: 3000, taxes_and_fees: 540, convenience_fee: 399, promotional_discount: 100, total_fare: 3839, is_cheapest: false, markup_vs_direct: 299 },
      },
    },
    {
      flight_number: "6E-532",
      carrier_code: "6E",
      carrier_name: "IndiGo",
      origin_airport: "DEL",
      destination_airport: "BOM",
      travel_date: "2026-09-18",
      departure_time: "09:30",
      arrival_time: "11:45",
      canonical_median_fare: 4427.6,
      min_walkaway_fare: 3717.0,
      max_observed_fare: 4712.0,
      carrier_direct_fare: 3717.0,
      spread_inr: 995.0,
      spread_pct: 22.5,
      cheapest_source: "Carrier Direct (IndiGo)",
      sources_count: 7,
      platform_matrix: {
        "Carrier Direct": { source_name: "Carrier Direct", source_domain: "goindigo.in", base_fare: 3150, taxes_and_fees: 567, convenience_fee: 0, promotional_discount: 0, total_fare: 3717, is_cheapest: true, markup_vs_direct: 0 },
        "EaseMyTrip": { source_name: "EaseMyTrip", source_domain: "easemytrip.com", base_fare: 3150, taxes_and_fees: 567, convenience_fee: 0, promotional_discount: 0, total_fare: 3717, is_cheapest: true, markup_vs_direct: 0 },
        "Skyscanner": { source_name: "Skyscanner India", source_domain: "skyscanner.co.in", base_fare: 3150, taxes_and_fees: 567, convenience_fee: 0, promotional_discount: 0, total_fare: 3767, is_cheapest: false, markup_vs_direct: 50 },
        "Cleartrip": { source_name: "Cleartrip", source_domain: "cleartrip.com", base_fare: 3150, taxes_and_fees: 567, convenience_fee: 349, promotional_discount: 150, total_fare: 3916, is_cheapest: false, markup_vs_direct: 199 },
        "Ixigo": { source_name: "Ixigo Flights", source_domain: "ixigo.com", base_fare: 3120, taxes_and_fees: 567, convenience_fee: 360, promotional_discount: 120, total_fare: 3927, is_cheapest: false, markup_vs_direct: 210 },
        "MakeMyTrip": { source_name: "MakeMyTrip India", source_domain: "makemytrip.com", base_fare: 3150, taxes_and_fees: 567, convenience_fee: 420, promotional_discount: 150, total_fare: 3987, is_cheapest: false, markup_vs_direct: 270 },
        "Yatra": { source_name: "Yatra Online", source_domain: "yatra.com", base_fare: 3150, taxes_and_fees: 567, convenience_fee: 399, promotional_discount: 100, total_fare: 4016, is_cheapest: false, markup_vs_direct: 299 },
      },
    },
    {
      flight_number: "AI-806",
      carrier_code: "AI",
      carrier_name: "Air India",
      origin_airport: "DEL",
      destination_airport: "BOM",
      travel_date: "2026-09-18",
      departure_time: "11:00",
      arrival_time: "13:10",
      canonical_median_fare: 4851.0,
      min_walkaway_fare: 4071.0,
      max_observed_fare: 5170.0,
      carrier_direct_fare: 4071.0,
      spread_inr: 1099.0,
      spread_pct: 22.7,
      cheapest_source: "Carrier Direct (Air India)",
      sources_count: 7,
      platform_matrix: {
        "Carrier Direct": { source_name: "Carrier Direct", source_domain: "airindia.com", base_fare: 3450, taxes_and_fees: 621, convenience_fee: 0, promotional_discount: 0, total_fare: 4071, is_cheapest: true, markup_vs_direct: 0 },
        "EaseMyTrip": { source_name: "EaseMyTrip", source_domain: "easemytrip.com", base_fare: 3450, taxes_and_fees: 621, convenience_fee: 0, promotional_discount: 0, total_fare: 4071, is_cheapest: true, markup_vs_direct: 0 },
        "Skyscanner": { source_name: "Skyscanner India", source_domain: "skyscanner.co.in", base_fare: 3450, taxes_and_fees: 621, convenience_fee: 0, promotional_discount: 0, total_fare: 4121, is_cheapest: false, markup_vs_direct: 50 },
        "Cleartrip": { source_name: "Cleartrip", source_domain: "cleartrip.com", base_fare: 3450, taxes_and_fees: 621, convenience_fee: 349, promotional_discount: 150, total_fare: 4270, is_cheapest: false, markup_vs_direct: 199 },
        "Ixigo": { source_name: "Ixigo Flights", source_domain: "ixigo.com", base_fare: 3420, taxes_and_fees: 621, convenience_fee: 360, promotional_discount: 120, total_fare: 4281, is_cheapest: false, markup_vs_direct: 210 },
        "MakeMyTrip": { source_name: "MakeMyTrip India", source_domain: "makemytrip.com", base_fare: 3450, taxes_and_fees: 621, convenience_fee: 420, promotional_discount: 150, total_fare: 4341, is_cheapest: false, markup_vs_direct: 270 },
        "Yatra": { source_name: "Yatra Online", source_domain: "yatra.com", base_fare: 3450, taxes_and_fees: 621, convenience_fee: 399, promotional_discount: 100, total_fare: 4370, is_cheapest: false, markup_vs_direct: 299 },
      },
    },
    {
      flight_number: "QP-1102",
      carrier_code: "QP",
      carrier_name: "Akasa Air",
      origin_airport: "DEL",
      destination_airport: "BOM",
      travel_date: "2026-09-18",
      departure_time: "14:15",
      arrival_time: "16:30",
      canonical_median_fare: 4027.0,
      min_walkaway_fare: 3363.0,
      max_observed_fare: 4320.0,
      carrier_direct_fare: 3363.0,
      spread_inr: 957.0,
      spread_pct: 23.8,
      cheapest_source: "Carrier Direct (Akasa Air)",
      sources_count: 7,
      platform_matrix: {
        "Carrier Direct": { source_name: "Carrier Direct", source_domain: "akasaair.com", base_fare: 2850, taxes_and_fees: 513, convenience_fee: 0, promotional_discount: 0, total_fare: 3363, is_cheapest: true, markup_vs_direct: 0 },
        "EaseMyTrip": { source_name: "EaseMyTrip", source_domain: "easemytrip.com", base_fare: 2850, taxes_and_fees: 513, convenience_fee: 0, promotional_discount: 0, total_fare: 3363, is_cheapest: true, markup_vs_direct: 0 },
        "Skyscanner": { source_name: "Skyscanner India", source_domain: "skyscanner.co.in", base_fare: 2850, taxes_and_fees: 513, convenience_fee: 0, promotional_discount: 0, total_fare: 3413, is_cheapest: false, markup_vs_direct: 50 },
        "Cleartrip": { source_name: "Cleartrip", source_domain: "cleartrip.com", base_fare: 2850, taxes_and_fees: 513, convenience_fee: 349, promotional_discount: 150, total_fare: 3562, is_cheapest: false, markup_vs_direct: 199 },
        "Ixigo": { source_name: "Ixigo Flights", source_domain: "ixigo.com", base_fare: 2850, taxes_and_fees: 513, convenience_fee: 360, promotional_discount: 120, total_fare: 3603, is_cheapest: false, markup_vs_direct: 240 },
        "MakeMyTrip": { source_name: "MakeMyTrip India", source_domain: "makemytrip.com", base_fare: 2850, taxes_and_fees: 513, convenience_fee: 420, promotional_discount: 150, total_fare: 3633, is_cheapest: false, markup_vs_direct: 270 },
        "Yatra": { source_name: "Yatra Online", source_domain: "yatra.com", base_fare: 2850, taxes_and_fees: 513, convenience_fee: 399, promotional_discount: 100, total_fare: 3662, is_cheapest: false, markup_vs_direct: 299 },
      },
    },
    {
      flight_number: "SG-8169",
      carrier_code: "SG",
      carrier_name: "SpiceJet",
      origin_airport: "DEL",
      destination_airport: "BOM",
      travel_date: "2026-09-18",
      departure_time: "18:45",
      arrival_time: "21:00",
      canonical_median_fare: 3942.0,
      min_walkaway_fare: 3292.0,
      max_observed_fare: 4235.0,
      carrier_direct_fare: 3292.0,
      spread_inr: 943.0,
      spread_pct: 23.9,
      cheapest_source: "Carrier Direct (SpiceJet)",
      sources_count: 7,
      platform_matrix: {
        "Carrier Direct": { source_name: "Carrier Direct", source_domain: "spicejet.com", base_fare: 2790, taxes_and_fees: 502, convenience_fee: 0, promotional_discount: 0, total_fare: 3292, is_cheapest: true, markup_vs_direct: 0 },
        "EaseMyTrip": { source_name: "EaseMyTrip", source_domain: "easemytrip.com", base_fare: 2790, taxes_and_fees: 502, convenience_fee: 0, promotional_discount: 0, total_fare: 3292, is_cheapest: true, markup_vs_direct: 0 },
        "Skyscanner": { source_name: "Skyscanner India", source_domain: "skyscanner.co.in", base_fare: 2790, taxes_and_fees: 502, convenience_fee: 0, promotional_discount: 0, total_fare: 3342, is_cheapest: false, markup_vs_direct: 50 },
        "Cleartrip": { source_name: "Cleartrip", source_domain: "cleartrip.com", base_fare: 2790, taxes_and_fees: 502, convenience_fee: 349, promotional_discount: 150, total_fare: 3491, is_cheapest: false, markup_vs_direct: 199 },
        "Ixigo": { source_name: "Ixigo Flights", source_domain: "ixigo.com", base_fare: 2790, taxes_and_fees: 502, convenience_fee: 360, promotional_discount: 120, total_fare: 3532, is_cheapest: false, markup_vs_direct: 240 },
        "MakeMyTrip": { source_name: "MakeMyTrip India", source_domain: "makemytrip.com", base_fare: 2790, taxes_and_fees: 502, convenience_fee: 420, promotional_discount: 150, total_fare: 3562, is_cheapest: false, markup_vs_direct: 270 },
        "Yatra": { source_name: "Yatra Online", source_domain: "yatra.com", base_fare: 2790, taxes_and_fees: 502, convenience_fee: 399, promotional_discount: 100, total_fare: 3591, is_cheapest: false, markup_vs_direct: 299 },
      },
    },
  ]);

  useEffect(() => {
    async function loadDetail() {
      const d = await fetchFromApi<RouteDetailResponse>(`/routes/${routeCode}`, detail);
      if (d) setDetail(d);

      const otaRes = await fetchFromApi<OTACommonFlightsResponse>(
        `/ota/common-flights?route_code=${routeCode}&horizon=${otaHorizon}`
      );
      if (otaRes && otaRes.common_flights && otaRes.common_flights.length > 0) {
        setOtaFlights(otaRes.common_flights);
      }
    }
    loadDetail();
  }, [routeCode, otaHorizon]);

  const fd = detail.fare_decomposition || {
    base_fare: 5372.65,
    fuel_surcharge: 1007.37,
    gst_taxes: 335.79,
    udf_adf: 350.0,
    convenience_fee: 92.0,
    total_consumer_fare: 7157.81,
  };
  const totalFare = fd.total_consumer_fare || 7157.81;

  const basePct = Math.round((fd.base_fare / totalFare) * 100);
  const fuelPct = Math.round((fd.fuel_surcharge / totalFare) * 100);
  const udfPct = Math.round((fd.udf_adf / totalFare) * 100);
  const gstPct = Math.round((fd.gst_taxes / totalFare) * 100);
  const feePct = Math.max(1, 100 - (basePct + fuelPct + udfPct + gstPct));

  return (
    <div className="space-y-8">
      {/* Navigation Breadcrumb */}
      <div>
        <Link
          href="/corridors"
          className="inline-flex items-center gap-1.5 text-xs font-sans font-medium text-mid-gray hover:text-ink transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to All Corridors</span>
        </Link>
      </div>

      {/* Corridor Header */}
      <SectionHeader
        title={`${routeCode} — ${detail.origin} ↔ ${detail.destination}`}
        headline={`Comprehensive tariff anatomy, multi-OTA common flight prices, and statutory fee decomposition for ${routeCode}.`}
        badge={`${detail.weight_pct}% DGCA WEIGHT`}
        badgeVariant="solid"
      />

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Basic Economy Fare"
          value={`₹${Math.round(fd.base_fare).toLocaleString()}`}
          subtitle="Median basic fare (T+15 anchor)"
          icon={<Plane className="h-6 w-6" />}
          badge="Pure Tariff"
          badgeVariant="neutral"
        />
        <StatCard
          title="Total Consumer Fare"
          value={`₹${Math.round(totalFare).toLocaleString()}`}
          subtitle="Out-of-pocket cost with all fees & taxes"
          icon={<DollarSign className="h-6 w-6" />}
          badge="Mandatory Price"
          badgeVariant="neutral"
        />
        <StatCard
          title="DGCA Volume Weight"
          value={`${detail.weight_pct}%`}
          subtitle="Share of total domestic basket traffic"
          icon={<Layers className="h-6 w-6" />}
          badge={detail.corridor_type === "METRO_TRUNK" ? "Trunk Metro" : "Regional Thin"}
          badgeVariant={detail.corridor_type === "METRO_TRUNK" ? "neutral" : "warning"}
        />
        <StatCard
          title="Multi-Platform Feeds"
          value="7 Sources"
          subtitle="Direct Carrier + 6 Major OTAs"
          icon={<CheckCircle2 className="h-6 w-6" />}
          badge="Harmonized"
          badgeVariant="success"
        />
      </div>

      {/* Fare Anatomy Decomposition (Component Separation) */}
      <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <PieChart className="h-4 w-4 text-ink" />
              <h3 className="text-sm font-semibold text-ink font-sans">
                Statutory Fare Decomposition & Levy Attribution
              </h3>
            </div>
            <p className="text-xs text-mid-gray font-sans mt-0.5">
              Isolating airline tariff inflation from government excise, airport development fees, and mandatory surcharges.
            </p>
          </div>
          <Badge variant="secondary" size="sm">
            100% UNBUNDLED AUDIT
          </Badge>
        </div>

        {/* Visual Stacked Progress Bar */}
        <div className="space-y-2">
          <div className="h-4 w-full rounded-full overflow-hidden flex bg-canvas border border-hairline">
            <div style={{ width: `${basePct}%` }} className="bg-ink" title={`Base Fare: ${basePct}%`} />
            <div style={{ width: `${fuelPct}%` }} className="bg-neutral-600" title={`Fuel Surcharge: ${fuelPct}%`} />
            <div style={{ width: `${udfPct}%` }} className="bg-neutral-400" title={`UDF/ADF: ${udfPct}%`} />
            <div style={{ width: `${gstPct}%` }} className="bg-neutral-300" title={`GST Taxes: ${gstPct}%`} />
            <div style={{ width: `${feePct}%` }} className="bg-neutral-200" title={`Convenience Fee: ${feePct}%`} />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 text-xs font-mono pt-1 text-mid-gray">
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-ink" />
              <span>Base Fare: <strong className="text-ink">{basePct}%</strong></span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-neutral-600" />
              <span>Fuel Surcharge: <strong className="text-ink">{fuelPct}%</strong></span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-neutral-400" />
              <span>Airport UDF/ADF: <strong className="text-ink">{udfPct}%</strong></span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-neutral-300" />
              <span>GST Taxes: <strong className="text-ink">{gstPct}%</strong></span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-neutral-200" />
              <span>Fees: <strong className="text-ink">{feePct}%</strong></span>
            </div>
          </div>
        </div>

        {/* Detailed Breakdown Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 pt-2">
          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-mid-gray font-sans">
              <Plane className="h-3.5 w-3.5 text-ink" />
              <span>Airline Base Fare</span>
            </div>
            <div className="text-lg font-bold font-mono text-ink">₹{Math.round(fd.base_fare).toLocaleString()}</div>
            <p className="text-[11px] text-mid-gray font-sans">Retained by carrier for flight operation.</p>
          </div>

          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-mid-gray font-sans">
              <Fuel className="h-3.5 w-3.5 text-ink" />
              <span>Fuel Surcharge</span>
            </div>
            <div className="text-lg font-bold font-mono text-ink">₹{Math.round(fd.fuel_surcharge).toLocaleString()}</div>
            <p className="text-[11px] text-mid-gray font-sans">Carrier fuel volatility hedge surcharge.</p>
          </div>

          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-mid-gray font-sans">
              <Building className="h-3.5 w-3.5 text-ink" />
              <span>Airport UDF / ADF</span>
            </div>
            <div className="text-lg font-bold font-mono text-ink">₹{Math.round(fd.udf_adf).toLocaleString()}</div>
            <p className="text-[11px] text-mid-gray font-sans">User development levy paid to airport operator.</p>
          </div>

          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-mid-gray font-sans">
              <Receipt className="h-3.5 w-3.5 text-ink" />
              <span>GST Taxes</span>
            </div>
            <div className="text-lg font-bold font-mono text-ink">₹{Math.round(fd.gst_taxes).toLocaleString()}</div>
            <p className="text-[11px] text-mid-gray font-sans">Statutory 5% GST on domestic economy travel.</p>
          </div>

          <div className="rounded-nested border border-hairline bg-canvas p-3.5 space-y-1">
            <div className="flex items-center gap-1.5 text-xs text-mid-gray font-sans">
              <Scale className="h-3.5 w-3.5 text-ink" />
              <span>Convenience Fee</span>
            </div>
            <div className="text-lg font-bold font-mono text-ink">₹{Math.round(fd.convenience_fee).toLocaleString()}</div>
            <p className="text-[11px] text-mid-gray font-sans">Mandatory portal booking/payment processing fee.</p>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MULTI-OTA COMMON FLIGHT PRICE MATRIX */}
      {/* ========================================================================= */}
      <div className="rounded-cards border border-hairline bg-paper p-6 sm:p-7 shadow-subtle space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-ink" />
              <h3 className="text-base font-semibold text-ink font-sans">
                Cross-Platform Common Flight Price Matrix & Canonical Fair-Fare Resolution
              </h3>
            </div>
            <p className="text-xs text-mid-gray font-sans mt-0.5">
              Side-by-side consumer price comparison of common physical flights across Direct Carrier portals and 6 leading OTAs.
            </p>
          </div>

          {/* Horizon Selector */}
          <div className="flex items-center gap-1 rounded-[18px] border border-hairline bg-canvas p-1 self-start sm:self-auto">
            <span className="text-[11px] font-mono text-mid-gray px-2">Booking Window:</span>
            {([1, 7, 15, 30, 45] as const).map((h) => (
              <button
                key={h}
                onClick={() => setOtaHorizon(h)}
                className={`rounded-[18px] px-3 py-1 text-xs font-sans font-medium transition-all ${
                  otaHorizon === h
                    ? "bg-ink text-paper shadow-subtle"
                    : "text-mid-gray hover:text-ink"
                }`}
              >
                T+{h}
              </button>
            ))}
          </div>
        </div>

        {/* Common Flights Price Matrix Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-hairline text-mid-gray font-sans uppercase tracking-[0.6px] text-[11px]">
                <th className="pb-3.5 font-medium">Flight Segment</th>
                <th className="pb-3.5 font-medium">Times</th>
                <th className="pb-3.5 font-medium">Carrier Direct</th>
                <th className="pb-3.5 font-medium">MakeMyTrip</th>
                <th className="pb-3.5 font-medium">EaseMyTrip</th>
                <th className="pb-3.5 font-medium">Ixigo</th>
                <th className="pb-3.5 font-medium">Yatra</th>
                <th className="pb-3.5 font-medium">Cleartrip</th>
                <th className="pb-3.5 font-medium">Skyscanner</th>
                <th className="pb-3.5 font-medium">Canonical Median</th>
                <th className="pb-3.5 font-medium text-right">Cheapest Channel</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {otaFlights.map((fl) => {
                const mat = fl.platform_matrix || {};
                const getVal = (name: string) => {
                  for (const [k, v] of Object.entries(mat)) {
                    if (k.toLowerCase().includes(name.toLowerCase())) {
                      return v;
                    }
                  }
                  return null;
                };

                const direct = getVal("Direct");
                const mmt = getVal("MakeMyTrip");
                const emt = getVal("EaseMyTrip");
                const ixigo = getVal("Ixigo");
                const yatra = getVal("Yatra");
                const clear = getVal("Cleartrip");
                const skyscanner = getVal("Skyscanner");

                return (
                  <tr key={fl.flight_number} className="hover:bg-canvas transition-colors">
                    {/* Flight & Airline */}
                    <td className="py-3.5">
                      <div className="font-mono font-bold text-ink text-sm">{fl.flight_number}</div>
                      <div className="text-mid-gray text-[11px]">{fl.carrier_name}</div>
                    </td>

                    {/* Times */}
                    <td className="py-3.5 font-mono text-mid-gray text-xs">
                      <div>{fl.departure_time} &rarr; {fl.arrival_time}</div>
                      <div className="text-[10px] text-mid-gray">Non-stop</div>
                    </td>

                    {/* Carrier Direct */}
                    <td className="py-3.5 font-mono text-xs">
                      {direct ? (
                        direct.is_cheapest ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                            ₹{Math.round(direct.total_fare).toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-ink-soft">
                            ₹{Math.round(direct.total_fare).toLocaleString()}
                          </span>
                        )
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* MakeMyTrip */}
                    <td className="py-3.5 font-mono text-xs">
                      {mmt ? (
                        mmt.is_cheapest ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                            ₹{Math.round(mmt.total_fare).toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-ink-soft">
                            ₹{Math.round(mmt.total_fare).toLocaleString()}
                          </span>
                        )
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* EaseMyTrip */}
                    <td className="py-3.5 font-mono text-xs">
                      {emt ? (
                        emt.is_cheapest ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                            ₹{Math.round(emt.total_fare).toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-ink-soft">
                            ₹{Math.round(emt.total_fare).toLocaleString()}
                          </span>
                        )
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* Ixigo */}
                    <td className="py-3.5 font-mono text-xs">
                      {ixigo ? (
                        ixigo.is_cheapest ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                            ₹{Math.round(ixigo.total_fare).toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-ink-soft">
                            ₹{Math.round(ixigo.total_fare).toLocaleString()}
                          </span>
                        )
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* Yatra */}
                    <td className="py-3.5 font-mono text-xs">
                      {yatra ? (
                        yatra.is_cheapest ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                            ₹{Math.round(yatra.total_fare).toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-ink-soft">
                            ₹{Math.round(yatra.total_fare).toLocaleString()}
                          </span>
                        )
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* Cleartrip */}
                    <td className="py-3.5 font-mono text-xs">
                      {clear ? (
                        clear.is_cheapest ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                            ₹{Math.round(clear.total_fare).toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-ink-soft">
                            ₹{Math.round(clear.total_fare).toLocaleString()}
                          </span>
                        )
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* Skyscanner */}
                    <td className="py-3.5 font-mono text-xs">
                      {skyscanner ? (
                        skyscanner.is_cheapest ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-[12px] border border-emerald-200/60">
                            ₹{Math.round(skyscanner.total_fare).toLocaleString()}
                          </span>
                        ) : (
                          <span className="text-ink-soft">
                            ₹{Math.round(skyscanner.total_fare).toLocaleString()}
                          </span>
                        )
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* Canonical Median (MoSPI Official) */}
                    <td className="py-3.5 font-mono font-bold text-ink text-sm bg-surface-alt/70 px-2 rounded-nested">
                      ₹{Math.round(fl.canonical_median_fare).toLocaleString()}
                    </td>

                    {/* Cheapest Platform Badge */}
                    <td className="py-3.5 text-right">
                      <Badge variant="success" size="sm">
                        {fl.cheapest_source.replace("Carrier Direct", "Direct")}
                      </Badge>
                      <div className="font-mono text-[10px] text-mid-gray mt-0.5">
                        Min ₹{Math.round(fl.min_walkaway_fare).toLocaleString()}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Methodological Context Note */}
        <div className="rounded-nested border border-hairline bg-canvas p-4 text-xs font-sans text-mid-gray leading-relaxed flex items-start gap-2.5">
          <Scale className="h-4 w-4 text-ink shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-ink block text-xs">
              MoSPI CPI Canonical Fair-Fare Resolution Methodology
            </span>
            <p className="mt-0.5 text-[11px]">
              Different OTAs charge convenience fees ranging from <strong className="text-ink">₹0 (EaseMyTrip / Carrier Direct)</strong> to <strong className="text-ink">₹420 (MakeMyTrip)</strong>, alongside promotional bank coupons. Under official CPI statistical standards, the <strong className="text-ink">Harmonized Platform Median</strong> is utilized as the primary index price relative because it is mathematically immune to single-platform pricing spikes, phantom promo codes, or fee gouging.
            </p>
          </div>
        </div>
      </div>

      {/* Carrier Head-to-Head Comparison Table */}
      <div className="rounded-cards border border-hairline bg-paper p-6 shadow-subtle space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ink font-sans">
              Airline Competitive Pricing & Capacity Share
            </h3>
            <p className="text-xs text-mid-gray font-sans">
              Direct comparison of basic economy and flexi tiers observed across scheduled carriers on this sector.
            </p>
          </div>
          <Badge variant="secondary" size="sm">
            T+15 Standard Anchor
          </Badge>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-hairline text-mid-gray font-sans uppercase tracking-[0.6px] text-[11px]">
                <th className="pb-3 font-medium">Carrier</th>
                <th className="pb-3 font-medium">Basic Economy Fare</th>
                <th className="pb-3 font-medium">Flexi / Business Tier</th>
                <th className="pb-3 font-medium">Daily Flight Frequency</th>
                <th className="pb-3 font-medium text-right">Value Designation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline font-sans">
              {detail.carrier_breakdown.map((c) => (
                <tr key={c.carrier} className="hover:bg-canvas transition-colors">
                  <td className="py-3">
                    <span className="font-mono font-bold text-ink">{c.name}</span>
                    <span className="text-[11px] text-mid-gray font-mono ml-1.5">({c.carrier})</span>
                  </td>
                  <td className="py-3 font-mono font-semibold text-ink text-sm">
                    ₹{c.basic_fare.toLocaleString()}
                  </td>
                  <td className="py-3 font-mono text-mid-gray">
                    ₹{c.flexi_fare.toLocaleString()}
                  </td>
                  <td className="py-3 font-mono text-ink">
                    {c.flights} Daily Services
                  </td>
                  <td className="py-3 text-right">
                    {c.is_min ? (
                      <Badge variant="success" size="sm">
                        Lowest Base Fare
                      </Badge>
                    ) : (
<Badge variant="secondary" size="sm">
                        Standard Tier
                      </Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
