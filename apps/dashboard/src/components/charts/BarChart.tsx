"use client";

import React, { useState, useEffect } from "react";
import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface BarChartProps {
  data: Array<Record<string, any>>;
  xKey: string;
  yKey: string;
  height?: number;
  valueSuffix?: string;
  colorMap?: Record<string, string>;
  defaultColor?: string;
}

export function BarChart({
  data,
  xKey,
  yKey,
  height = 240,
  valueSuffix = "",
  colorMap = {},
  defaultColor = "#171717",
}: BarChartProps) {
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
        <RechartsBarChart
          data={data}
          margin={{ top: 15, right: 15, left: -20, bottom: 25 }}
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
            tickLine={false}
            axisLine={false}
            stroke="#64748b"
            fontSize={11}
            tickMargin={8}
            fontFamily="var(--font-sans)"
          />
          <Tooltip
            content={({ active, payload, label }) => {
              if (active && payload && payload.length) {
                const item = payload[0];
                return (
                  <div className="rounded-[14px] border border-slate-700/80 bg-[#0f172a]/95 backdrop-blur-xl p-3 shadow-2xl font-sans text-xs">
                    <div className="text-slate-400 text-[11px] mb-1 font-mono font-medium">{label}</div>
                    <div className="text-white font-bold text-sm flex items-center gap-1.5 font-mono">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: (item.payload && colorMap[item.payload[xKey]]) || defaultColor }}
                      />
                      <span>{item.value}{valueSuffix}</span>
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
          <Bar
            dataKey={yKey}
            radius={[4, 4, 0, 0]}
          >
            {data.map((entry, index) => {
              const fill = colorMap[entry[xKey]] || defaultColor;
              return <Cell key={`cell-${index}`} fill={fill} />;
            })}
          </Bar>
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
}

