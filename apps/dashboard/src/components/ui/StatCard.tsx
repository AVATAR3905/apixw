"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/Card";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode | React.ComponentType<{ className?: string }>;
  trend?: {
    value: string;
    direction: "up" | "down" | "neutral";
    label?: string;
  };
  change?: number;
  changeLabel?: string;
  changeInverted?: boolean;
  accent?: string;
  badge?: string;
  badgeVariant?: "success" | "warning" | "danger" | "info" | "neutral" | "safe";
  className?: string;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  change,
  changeLabel,
  changeInverted,
  accent,
  badge,
  badgeVariant = "neutral",
  className,
}: StatCardProps) {
  return (
    <Card className={cn("group relative overflow-hidden transition-all hover:shadow-xl hover:border-orange-500/20", className)}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
              {title}
            </p>
            <p className="text-3xl font-bold text-foreground tabular-nums mb-1">
              {value}
            </p>
            {change !== undefined && (
              <div className="flex items-center gap-1.5 mt-1">
                <span
                  className={cn(
                    "flex items-center gap-1 text-xs font-bold font-mono",
                    changeInverted
                      ? change >= 0
                        ? "text-red-400"
                        : "text-emerald-400"
                      : change >= 0
                      ? "text-emerald-400"
                      : "text-red-400"
                  )}
                >
                  {change >= 0 ? "+" : ""}
                  {change.toFixed(2)}%
                </span>
                {changeLabel && <span className="text-xs text-muted-foreground">{changeLabel}</span>}
              </div>
            )}
            {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
            {trend && (
              <div className="flex items-center gap-1.5 mt-2">
                <span className={cn(
                  "flex items-center gap-1 text-xs font-semibold",
                  trend.direction === "up" && "text-emerald-400",
                  trend.direction === "down" && "text-red-400",
                  trend.direction === "neutral" && "text-muted-foreground"
                )}>
                  {trend.direction === "up" && (
                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <polyline points="23 6 12 17 5 6" />
                    </svg>
                  )}
                  {trend.direction === "down" && (
                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <polyline points="23 18 12 7 5 18" />
                    </svg>
                  )}
                  {trend.direction === "neutral" && (
                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                  )}
                  <span>{trend.value}</span>
                  {trend.label && <span className="text-muted-foreground">{trend.label}</span>}
                </span>
              </div>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            {icon && (
              <div className="p-3 rounded-xl bg-gradient-to-br from-orange-500/20 to-amber-500/20 text-orange-400 group-hover:from-orange-500/30 group-hover:to-amber-500/30 transition-all">
                {React.isValidElement(icon)
                  ? icon
                  : React.createElement(icon as React.ComponentType<{ className?: string }>, { className: "h-6 w-6" })}
              </div>
            )}
            {badge && (
              <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono font-semibold rounded ${{
                success: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30",
                warning: "bg-amber-500/10 text-amber-400 border border-amber-500/30",
                danger: "bg-red-500/10 text-red-400 border border-red-500/30",
                info: "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30",
                neutral: "bg-slate-500/10 text-slate-400 border border-slate-500/30",
                safe: "bg-emerald-500/15 text-emerald-300 border border-emerald-400/40",
              }[badgeVariant]}`}>
                {badge}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}