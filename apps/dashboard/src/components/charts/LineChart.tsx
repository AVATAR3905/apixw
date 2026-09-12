"use client";

import React, { useState, useEffect } from "react";
import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export interface SeriesConfig {
  key: string;
  name: string;
  color: string;
  strokeWidth?: number;
  strokeDasharray?: string;
}

interface LineChartProps {
  data: Array<Record<string, any>>;
  xKey: string;
  series: SeriesConfig[];
  height?: number;
  yDomain?: [number | "auto", number | "auto"];
  valuePrefix?: string;
  valueSuffix?: string;
  yTickFormatter?: (val: any) => string;
}

export function LineChart({
  data,
  xKey,
  series,
  height = 280,
  yDomain = ["auto", "auto"],
  valuePrefix = "",
  valueSuffix = "",
  yTickFormatter,
}: LineChartProps) {
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
        Loading chart...
      </div>
    );
  }

  return (
    <div style={{ height, width: "100%" }} className="relative">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsLineChart
          data={data}
          margin={{ top: 15, right: 15, left: -15, bottom: 0 }}
        >
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
                return (
                  <div className="rounded-[14px] border border-slate-700/80 bg-[#0f172a]/95 backdrop-blur-xl p-3 shadow-2xl font-sans text-xs space-y-1.5 min-w-[170px]">
                    <div className="text-slate-400 text-[11px] font-mono font-medium border-b border-slate-800 pb-1">
                      {label}
                    </div>
                    {payload.map((entry) => (
                      <div
                        key={entry.dataKey as string}
                        className="flex items-center justify-between gap-3 text-xs"
                      >
                        <span className="flex items-center gap-1.5 text-slate-300">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: entry.color }}
                          />
                          <span>{entry.name}:</span>
                        </span>
                        <span className="font-mono font-semibold text-white">
                          {valuePrefix}{entry.value}{valueSuffix}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              }
              return null;
            }}
          />
          <Legend
            verticalAlign="top"
            align="right"
            iconType="circle"
            wrapperStyle={{
              paddingBottom: "12px",
              fontSize: "11px",
              fontFamily: "var(--font-sans)",
              color: "#94a3b8",
            }}
          />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={s.color}
              strokeWidth={s.strokeWidth || 2}
              strokeDasharray={s.strokeDasharray}
              dot={{
                r: 3.5,
                fill: s.color,
                stroke: "#ffffff",
                strokeWidth: 1.5,
              }}
              activeDot={{
                r: 5,
                fill: s.color,
                stroke: "#ffffff",
                strokeWidth: 2,
              }}
            />
          ))}
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  );
}

