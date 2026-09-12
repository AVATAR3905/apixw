"use client";

import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;
const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden rounded-lg border border-border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-lg animate-in fade-in-0 zoom-in-95 data-[state=delayed-open]:animate-out data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
      "text-xs font-mono bg-card border-border"
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

interface InfoTooltipProps extends React.HTMLAttributes<HTMLSpanElement> {
  label?: string;
  tooltip?: string;
  children?: React.ReactNode;
}

function InfoTooltip({ label, tooltip, children }: InfoTooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={100}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>
          <span className="inline-flex cursor-help items-center gap-1.5 border-b border-dashed border-muted-foreground/40 text-sm text-foreground">
            {children ?? label}
          </span>
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Content
          sideOffset={4}
          className="z-50 max-w-xs overflow-hidden rounded-lg border border-border bg-card px-3 py-2 text-xs font-mono text-popover-foreground shadow-lg"
        >
          {tooltip}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider, InfoTooltip };