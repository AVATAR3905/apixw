"use client";

import React, { useState, useEffect } from "react";
import {
  AreaChart as RechartsAreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface AreaChartProps {
  data: Array<Record<string, any>>;
  xKey: string;
  yKey: string;
  height?: number;
  color?: "iris" | "cyan" | "emerald" | "amber";
  yDomain?: [number | "auto", number | "auto"];
  valuePrefix?: string;
  valueSuffix?: string;
  yTickFormatter?: (val: any) => string;
}

export function AreaChart({
  data,
  xKey,
  yKey,
  height = 240,
  color = "iris",
  yDomain = ["auto", "auto"],
  valuePrefix = "",
  valueSuffix = "",
  yTickFormatter,
}: AreaChartProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        style={{ height }}
        className="w-full rounded-nested bg-canvas border border-hairline animate-pulse flex items-center justify-center text-xs text-mid-gray font-sans"
      >
        Loading visualization...
      </div>
    );
  }

  const strokeMap: Record<string, string> = {
    iris: "#f97316",
    cyan: "#38bdf8",
    emerald: "#10b981",
    amber: "#f97316",
  };

  const gradientMap: Record<string, [string, string]> = {
    iris: ["rgba(249, 115, 22, 0.40)", "rgba(249, 115, 22, 0.02)"],
    cyan: ["rgba(56, 189, 248, 0.40)", "rgba(56, 189, 248, 0.02)"],
    emerald: ["rgba(16, 185, 129, 0.40)", "rgba(16, 185, 129, 0.02)"],
    amber: ["rgba(249, 115, 22, 0.45)", "rgba(249, 115, 22, 0.02)"],
  };

  const stroke = strokeMap[color] || "#f97316";
  const gradient = gradientMap[color] || gradientMap.iris;
  const gradientId = `area-gradient-${color}-${yKey}`;

  return (
    <div style={{ height, width: "100%" }} className="relative">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsAreaChart
          data={data}
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={gradient[0]} />
              <stop offset="95%" stopColor={gradient[1]} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#1e293b"
            vertical={false}
          />
          <XAxis
            dataKey={xKey}
            tickLine={false}
            axisLine={false}
            stroke="#64748b"
            fontSize={11}
            tickMargin={8}
            fontFamily="var(--font-sans)"
          />
          <YAxis
            domain={yDomain}
            tickLine={false}
            axisLine={false}
            stroke="#64748b"
            fontSize={11}
            tickMargin={8}
            fontFamily="var(--font-sans)"
            tickFormatter={yTickFormatter}
          />
          <Tooltip
            content={({ active, payload, label }) => {
              if (active && payload && payload.length) {
                const val = payload[0].value;
                return (
                  <div className="rounded-[14px] border border-slate-700/80 bg-[#0f172a]/95 backdrop-blur-xl p-3 shadow-2xl font-sans text-xs">
                    <div className="text-slate-400 text-[11px] mb-1 font-mono font-medium">{label}</div>
                    <div className="text-white font-bold text-sm flex items-center gap-1.5 font-mono">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: stroke }} />
                      <span>{valuePrefix}{val}{valueSuffix}</span>
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Area
            type="monotone"
            dataKey={yKey}
            stroke={stroke}
            strokeWidth={3}
            fillOpacity={1}
            fill={`url(#${gradientId})`}
            activeDot={{
              r: 5,
              stroke: "#0f172a",
              strokeWidth: 2.5,
              fill: stroke,
            }}
          />
        </RechartsAreaChart>
      </ResponsiveContainer>
    </div>
  );
}

