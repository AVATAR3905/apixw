"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";

interface SectionHeaderProps {
  title: string;
  headline?: string;
  badge?: string;
  badgeVariant?: "success" | "warning" | "danger" | "info" | "neutral" | "solid" | "soft";
  action?: React.ReactNode;
  className?: string;
}

export function SectionHeader({
  title,
  headline,
  badge,
  badgeVariant = "solid",
  action,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn("flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8", className)}>
      <div>
        <div className="flex items-center gap-2 mb-2">
          {badge && (
            <Badge variant={badgeVariant === "solid" ? "default" : badgeVariant} size="sm">
              {badge}
            </Badge>
          )}
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
            {title}
          </h2>
        </div>
        {headline && (
          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            {headline}
          </p>
        )}
      </div>
      {action && (
        <div className="shrink-0 mt-4 sm:mt-0">
          {action}
        </div>
      )}
    </div>
  );
}