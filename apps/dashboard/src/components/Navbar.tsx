"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Activity,
  Route,
  TrendingUp,
  ShieldCheck,
  Search,
  Menu,
  X,
  ChevronDown,
  Sparkles,
  BarChart3,
  FlaskConical,
  FileText,
  Settings,
  Zap,
  LineChart,
  Shield,
  Database,
  Globe,
  Clock,
  Gavel,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

interface NavChild {
  label: string;
  href: string;
  icon?: LucideIcon;
}

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  description?: string;
  badges?: string[];
  children?: NavChild[];
}

const navigation: NavItem[] = [
  {
    label: "Overview",
    href: "/",
    icon: Activity,
    description: "Real-time headline index & macro pulse",
    badges: ["LIVE"],
  },
  {
    label: "Forecast",
    href: "/forecast",
    icon: Sparkles,
    description: "28-day probabilistic forecast with P10-P90 bands",
    badges: ["NEW"],
  },
  {
    label: "Corridors",
    href: "/corridors",
    icon: Route,
    description: "10 DGCA routes with heatmaps & fare anatomy",
    children: [
      { label: "All Corridors", href: "/corridors" },
      { label: "DEL-BOM", href: "/corridors/DEL-BOM" },
      { label: "DEL-BLR", href: "/corridors/DEL-BLR" },
      { label: "BOM-BLR", href: "/corridors/BOM-BLR" },
      { label: "DEL-CCU", href: "/corridors/DEL-CCU" },
      { label: "DEL-HYD", href: "/corridors/DEL-HYD" },
      { label: "BOM-MAA", href: "/corridors/BOM-MAA" },
      { label: "BLR-HYD", href: "/corridors/BLR-HYD" },
      { label: "DEL-MAA", href: "/corridors/DEL-MAA" },
      { label: "DEL-IXS", href: "/corridors/DEL-IXS" },
      { label: "DEL-DHM", href: "/corridors/DEL-DHM" },
    ],
  },
  {
    label: "Market Intelligence",
    href: "/market-intelligence",
    icon: BarChart3,
    description: "Carrier dynamics, lead-time elasticity & volatility",
    children: [
      { label: "Carrier Power", href: "/carrier-inflation", icon: Zap },
      { label: "Lead-Time Curves", href: "/lead-time", icon: Clock },
      { label: "Volatility Heatmap", href: "/fluctuations", icon: LineChart },
      { label: "Fuel Overlay", href: "/fuel-context", icon: FlaskConical },
    ],
  },
  {
    label: "Data & Governance",
    href: "/governance",
    icon: ShieldCheck,
    description: "Pipeline health, CPI validation & quality metrics",
    children: [
      { label: "Pipeline Status", href: "/governance", icon: Database },
      { label: "CPI Validation", href: "/validation", icon: FileText },
      { label: "Data Quality", href: "/quality", icon: Shield },
      { label: "Source Registry", href: "/sources", icon: Globe },
      { label: "Methodology", href: "/methodology", icon: FlaskConical },
      { label: "Policy Insights", href: "/policy-insights", icon: Gavel },
    ],
  },
  {
    label: "Settings",
    href: "/settings",
    icon: Settings,
    description: "Configuration & API keys",
  },
];

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [corridorSelector, setCorridorSelector] = useState("");

  const corridorsList = [
    { code: "DEL-BOM", name: "Delhi ↔ Mumbai", type: "METRO" },
    { code: "DEL-BLR", name: "Delhi ↔ Bengaluru", type: "METRO" },
    { code: "BOM-BLR", name: "Mumbai ↔ Bengaluru", type: "METRO" },
    { code: "DEL-CCU", name: "Delhi ↔ Kolkata", type: "METRO" },
    { code: "DEL-HYD", name: "Delhi ↔ Hyderabad", type: "METRO" },
    { code: "BOM-MAA", name: "Mumbai ↔ Chennai", type: "METRO" },
    { code: "BLR-HYD", name: "Bengaluru ↔ Hyderabad", type: "METRO" },
    { code: "DEL-MAA", name: "Delhi ↔ Chennai", type: "METRO" },
    { code: "DEL-IXS", name: "Delhi ↔ Silchar", type: "REGIONAL" },
    { code: "DEL-DHM", name: "Delhi ↔ Dharamshala", type: "REGIONAL" },
  ];

  const handleCorridorJump = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val) {
      router.push(`/corridors/${val}`);
    }
  };

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl shadow-sm">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between px-4 sm:px-6 lg:px-8 py-3">
        {/* Brand */}
        <Link
          href="/"
          className="flex items-center gap-3 group py-1"
          aria-label="Phoenix Home"
        >
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 via-amber-500 to-red-600 shadow-lg shadow-orange-500/30 group-hover:shadow-orange-500/50 transition-all">
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-white" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" fill="currentColor" fillOpacity="0.8" />
            </svg>
          </div>
          <div className="hidden sm:block flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-base tracking-[0.12em] text-foreground font-sans">
                PHOENIX
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-orange-500/20 text-orange-400 border border-orange-500/30 font-semibold">
                QUANT
              </span>
            </div>
            <span className="text-[10px] font-mono tracking-wider text-muted-foreground font-medium -mt-0.5">
              AIRFARE OBSERVATORY
            </span>
          </div>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex items-center gap-0.5">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            const hasChildren = item.children && item.children.length > 0;
            const isOpen = openDropdown === item.href;

            const handleKeyDown = (e: React.KeyboardEvent) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                if (hasChildren) setOpenDropdown(isOpen ? null : item.href);
              }
            };

            if (hasChildren) {
              return (
                <div
                  key={item.href}
                  className="relative"
                  onMouseEnter={() => setHoveredItem(item.href)}
                  onMouseLeave={() => setHoveredItem(null)}
                >
                  <button
                    onClick={() => setOpenDropdown(isOpen ? null : item.href)}
                    onKeyDown={handleKeyDown}
                    className={cn(
                      "flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-medium transition-all",
                      active
                        ? "bg-gradient-to-r from-orange-500/20 to-amber-500/20 text-foreground border border-orange-500/30"
                        : "text-muted-foreground hover:text-foreground hover:bg-accent"
                    )}
                  >
                    <Icon className={cn("h-4 w-4 shrink-0", active ? "text-orange-400" : "text-muted-foreground")} />
                    <span>{item.label}</span>
                    <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform", isOpen && "rotate-180")} />
                  </button>

                  {/* Dropdown */}
                  {isOpen && (
                    <div className="absolute left-0 top-full z-50 mt-2 w-64 animate-in fade-in-0 zoom-in-95">
                      <div className="rounded-2xl border border-border bg-popover p-2 shadow-xl">
                        <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground font-mono font-semibold">
                          {item.label.toUpperCase()}
                        </div>
                        {item.children?.map((child) => (
                          <Link
                            key={child.href}
                            href={child.href}
                            onClick={() => setOpenDropdown(null)}
                            className={cn(
                              "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-all",
                              pathname === child.href
                                ? "bg-orange-500/20 text-foreground font-medium"
                                : "text-muted-foreground hover:text-foreground hover:bg-accent"
                            )}
                          >
                            {child.icon && <child.icon className="h-4 w-4 shrink-0 text-muted-foreground" />}
                            <span>{child.label}</span>
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            }

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium transition-all",
                  active
                    ? "bg-gradient-to-r from-orange-500/20 to-amber-500/20 text-foreground border border-orange-500/30 shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                )}
              >
                <Icon className={cn("h-4 w-4 shrink-0", active ? "text-orange-400" : "text-muted-foreground")} />
                <span>{item.label}</span>
                {item.badges && (
                  <span className="ml-auto flex gap-1">
                    {item.badges.map((badge) => (
                      <span
                        key={badge}
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 border border-orange-500/30 font-semibold"
                      >
                        {badge}
                      </span>
                    ))}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Quick Actions */}
        <div className="hidden lg:flex items-center gap-2">
          {/* Corridor Quick Select */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/50 pointer-events-none" />
            <select
              value={corridorSelector}
              onChange={handleCorridorJump}
              className="rounded-xl border border-border bg-background/50 pl-10 pr-8 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
              aria-label="Jump to Corridor"
            >
              <option value="" disabled>
                Jump to Corridor...
              </option>
              {corridorsList.map((c) => (
                <option key={c.code} value={c.code} className="bg-background text-foreground">
                  {c.code} — {c.name}
                </option>
              ))}
            </select>
          </div>

          {/* Live Status */}
          <div className="flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5">
            <span className="relative flex h-2 w-2">
              <span className="absolute inset-0 h-full w-full rounded-full bg-emerald-400 animate-pulse" />
              <span className="absolute inset-0 h-full w-full rounded-full bg-emerald-400/30 animate-ping" />
            </span>
            <span className="text-xs font-mono font-medium text-emerald-400">LIVE</span>
          </div>

          {/* Theme Toggle */}
          <Button variant="ghost" size="icon" className="rounded-xl">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M12 7a5 5 0 110 10 5 5 0 010-10z" />
            </svg>
          </Button>
        </div>

        {/* Mobile Menu Button */}
        <div className="lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-border bg-background/95 backdrop-blur-xl px-4 py-4 animate-in slide-in-from-top-2 duration-200">
          <div className="space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(
                    "flex items-start gap-3 rounded-xl p-3 transition-all",
                    active
                      ? "bg-gradient-to-r from-orange-500/15 to-amber-500/15 text-foreground font-medium border border-orange-500/30"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent"
                  )}
                >
                  <Icon className={cn("h-5 w-5 shrink-0 mt-0.5", active ? "text-orange-400" : "text-muted-foreground")} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-foreground truncate">{item.label}</div>
                    <div className="text-[11px] text-muted-foreground leading-tight mt-0.5">{item.description}</div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </header>
  );
}