"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = {
  default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
  secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
  destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
  outline: "text-foreground",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  danger: "border-red-500/30 bg-red-500/10 text-red-400",
  info: "border-cyan-500/30 bg-cyan-500/10 text-cyan-400",
  neutral: "border-slate-500/30 bg-slate-500/10 text-slate-400",
  soft: "border-transparent bg-muted text-foreground",
  safe: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
  solid: "border-transparent bg-gradient-to-r from-orange-500 to-amber-500 text-white",
};

export type BadgeVariant = keyof typeof badgeVariants;
export type BadgeSize = "xs" | "sm" | "md" | "lg";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
}

export function Badge({ className, variant = "default", size = "md", dot, children, ...props }: BadgeProps) {
  const sizeClasses = {
    xs: "px-1.5 py-0.5 text-[9px]",
    sm: "px-2 py-0.5 text-[10px]",
    md: "px-2.5 py-0.5 text-xs",
    lg: "px-3 py-1 text-sm",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border font-semibold transition-all",
        badgeVariants[variant],
        sizeClasses[size]
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn(
            "mr-1 h-1.5 w-1.5 rounded-full",
            variant === "success" || variant === "safe" ? "bg-emerald-400" :
            variant === "warning" ? "bg-amber-400" :
            variant === "danger" ? "bg-red-400" :
            variant === "info" ? "bg-cyan-400" :
            "bg-muted-foreground"
          )}
        />
      )}
      {children}
    </span>
  );
}