"use client";

import * as React from "react";
import {
  AreaChart as RechartsAreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from "recharts";
import { cn } from "@/lib/utils";

export interface ForecastChartDataPoint {
  date: string;
  baseVal: number;
  totalVal?: number;
  isForecast?: boolean;
  p10?: number;
  p25?: number;
  p50?: number;
  p75?: number;
  p90?: number;
  modelConfidence?: number;
}

interface ForecastChartProps {
  data: ForecastChartDataPoint[];
  xKey: string;
  yKey: "baseVal" | "totalVal";
  height?: number;
  color?: "iris" | "cyan" | "emerald" | "amber" | "orange";
  yDomain?: [number | "auto", number | "auto"];
  valuePrefix?: string;
  valueSuffix?: string;
  yTickFormatter?: (val: number) => string;
  showForecastBands?: boolean;
  showConfidence?: boolean;
  title?: string;
  subtitle?: string;
}

const colorMap = {
  iris: { stroke: "#a855f7", gradient: ["rgba(168, 85, 247, 0.4)", "rgba(168, 85, 247, 0.02)"] },
  cyan: { stroke: "#06b6d4", gradient: ["rgba(6, 182, 212, 0.4)", "rgba(6, 182, 212, 0.02)"] },
  emerald: { stroke: "#10b981", gradient: ["rgba(16, 185, 129, 0.4)", "rgba(16, 185, 129, 0.02)"] },
  amber: { stroke: "#f59e0b", gradient: ["rgba(245, 158, 11, 0.4)", "rgba(245, 158, 11, 0.02)"] },
  orange: { stroke: "#f97316", gradient: ["rgba(249, 115, 22, 0.4)", "rgba(249, 115, 22, 0.02)"] },
};

const forecastGradientMap: Record<string, string[]> = {
  iris: ["rgba(168, 85, 247, 0.15)", "rgba(168, 85, 247, 0.0)"],
  orange: ["rgba(249, 115, 22, 0.15)", "rgba(249, 115, 22, 0.0)"],
  amber: ["rgba(245, 158, 11, 0.15)", "rgba(245, 158, 11, 0.0)"],
  cyan: ["rgba(6, 182, 212, 0.15)", "rgba(6, 182, 212, 0.0)"],
  emerald: ["rgba(16, 185, 129, 0.15)", "rgba(16, 185, 129, 0.0)"],
};

export function ForecastChart(props: ForecastChartProps): JSX.Element {
  const {
    data,
    xKey,
    yKey,
    height = 300,
    color = "orange",
    yDomain = ["auto", "auto"],
    valuePrefix = "",
    valueSuffix = "",
    yTickFormatter,
    showForecastBands = true,
    showConfidence = true,
    title,
    subtitle,
  } = props;
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div style={{ height }} className="w-full rounded-2xl border border-border bg-card/50 animate-pulse flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <div className="h-8 w-8 animate-pulse rounded-full bg-muted mx-auto mb-2" />
          <p className="text-sm">Loading chart...</p>
        </div>
      </div>
    );
  }

  const { stroke, gradient } = colorMap[color];
  const forecastGradient = forecastGradientMap[color] || forecastGradientMap.orange;
  const gradientId = `area-gradient-${color}-${yKey}`;
  const forecastGradientId = `forecast-gradient-${color}-${yKey}`;
  const ciGradientId = `ci-gradient-${color}-${yKey}`;

  // Split data
  const historicalData = data.filter((d) => !d.isForecast);
  const forecastData = data.filter((d) => d.isForecast);

  // Prepare forecast data with CI bands
  const forecastWithBands = forecastData.map((d) => {
    const baseVal = d[yKey] ?? d.baseVal;
    return {
      ...d,
      p10: d.p10 ?? baseVal * 0.95,
      p90: d.p90 ?? baseVal * 1.05,
      p25: d.p25 ?? baseVal * 0.98,
      p75: d.p75 ?? baseVal * 1.02,
    };
  });

  const getField = (point: ForecastChartDataPoint, key: string) =>
    (point as unknown as Record<string, unknown>)[key] as number;

  // Find the transition point
  const lastHistorical = historicalData[historicalData.length - 1];
  const firstForecast = forecastData[0];

  return (
    <div className="w-full">
      {(title || subtitle) && (
        <div className="mb-4">
          {title && <h3 className="text-lg font-semibold text-foreground">{title}</h3>}
          {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
        </div>
      )}

      <div style={{ height, width: "100%" }} className="relative rounded-2xl border border-border bg-card overflow-hidden">
        <ResponsiveContainer width="100%" height="100%">
          <RechartsAreaChart
            data={data}
            margin={{ top: 10, right: 20, left: -10, bottom: 0 }}
          >
            <defs>
              {/* Historical gradient */}
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={gradient[0]} />
                <stop offset="95%" stopColor={gradient[1]} />
              </linearGradient>
              {/* Forecast gradient */}
              <linearGradient id={forecastGradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={forecastGradient[0]} />
                <stop offset="95%" stopColor={forecastGradient[1]} />
              </linearGradient>
              {/* Confidence interval gradient */}
              <linearGradient id={ciGradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(249, 115, 22, 0.12)" />
                <stop offset="100%" stopColor="rgba(249, 115, 22, 0.0)" />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="4 4"
              stroke="#1e293b"
              vertical={false}
              horizontal={true}
            />

            <XAxis
              dataKey={xKey}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#64748b", fontSize: 11, fontFamily: "var(--font-mono)" }}
              dy={8}
              tickMargin={4}
              interval="preserveStartEnd"
            />

            <YAxis
              domain={yDomain}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#64748b", fontSize: 11, fontFamily: "var(--font-mono)" }}
              tickFormatter={yTickFormatter || ((val) => `${valuePrefix}${val}${valueSuffix}`)}
              tickCount={5}
              width={60}
              dy={-10}
            />

            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const item = payload[0].payload;
                  const isForecast = item.isForecast;
                  const val = item[yKey];
                  const p10 = item.p10;
                  const p90 = item.p90;
                  const confidence = item.modelConfidence;
                  return (
                    <div className="rounded-xl border border-border bg-card p-3 shadow-xl font-sans text-xs">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="font-mono font-medium text-foreground">{label}</div>
                        {isForecast && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-orange-500/20 text-orange-400 border border-orange-500/30">
                            FORECAST
                          </span>
                        )}
                      </div>
                      <div className="text-white font-bold text-sm flex items-center gap-1.5 font-mono">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: stroke }} />
                        <span>{valuePrefix}{val?.toFixed(1) || "—"}</span>
                      </div>
                      {showForecastBands && isForecast && p10 !== undefined && p90 !== undefined && (
                        <div className="text-xs text-muted-foreground mt-2 font-mono flex items-center gap-2">
                          <span className="text-emerald-400">P10: {valuePrefix}{p10.toFixed(1)}</span>
                          <span className="text-red-400">P90: {valuePrefix}{p90.toFixed(1)}</span>
                        </div>
                      )}
                      {showConfidence && isForecast && (
                        <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                          <span className="flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-orange-400" />
                            Confidence: {(item.modelConfidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />

            {/* 90% Confidence Interval Band (Forecast) */}
            {showForecastBands && forecastWithBands.length > 0 && (
              <>
                <Area
                  type="monotone"
                  dataKey="p90"
                  stroke="none"
                  fillOpacity={1}
                  fill={`url(#${ciGradientId})`}
                  data={forecastWithBands}
                />
                <Area
                  type="monotone"
                  dataKey="p10"
                  stroke="none"
                  fill="#0f172a"
                  data={forecastWithBands}
                />
              </>
            )}

            {/* Historical Area */}
            <Area
              type="monotone"
              dataKey={yKey}
              stroke={stroke}
              strokeWidth={2.5}
              fillOpacity={1}
              fill={`url(#${gradientId})`}
              data={historicalData}
              activeDot={{
                r: 6,
                stroke: "#0f172a",
                strokeWidth: 2,
                fill: stroke,
              }}
            />

            {/* Forecast Median Line (dashed) */}
            {forecastWithBands.length > 0 && (
              <Line
                type="monotone"
                dataKey={yKey}
                stroke={stroke}
                strokeWidth={2.5}
                strokeDasharray="6 4"
                fill="none"
                data={forecastWithBands}
                activeDot={{
                  r: 6,
                  stroke: "#0f172a",
                  strokeWidth: 2,
                  fill: stroke,
                }}
              />
            )}

            {/* Transition connector line */}
            {lastHistorical && firstForecast && (
              <Line
                type="monotone"
                dataKey={yKey}
                stroke={stroke}
                strokeWidth={2}
                strokeDasharray="4 4"
                strokeOpacity={0.5}
                fill="none"
                data={[
                  { [xKey]: getField(lastHistorical, xKey), [yKey]: getField(lastHistorical, yKey) },
                  { [xKey]: getField(firstForecast, xKey), [yKey]: getField(firstForecast, yKey) },
                ]}
              />
            )}

            {/* Vertical reference line at forecast start */}
            {lastHistorical && (
              <ReferenceLine
                x={getField(lastHistorical, xKey)}
                stroke="rgba(249, 115, 22, 0.4)"
                strokeWidth={1}
                strokeDasharray="4 4"
                label={{
                  value: "FORECAST START",
                  position: "top",
                  fill: "#f97316",
                  fontSize: 9,
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                  offset: -10,
                }}
              />
            )}

            <Legend
              layout="horizontal"
              align="center"
              verticalAlign="bottom"
              iconType="line"
              wrapperStyle={{ paddingTop: 10, paddingBottom: 5 }}
              formatter={(value) => {
                if (value === yKey) return "Historical";
                if (value === "p50") return "Forecast (median)";
                if (value === "ci") return "80% CI";
                return value;
              }}
            />
          </RechartsAreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}