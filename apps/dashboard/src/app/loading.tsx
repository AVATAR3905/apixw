import React from "react";

export default function Loading() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header skeleton */}
      <div className="flex justify-between items-center border-b border-hairline pb-6">
        <div className="space-y-2">
          <div className="h-8 w-64 bg-paper border border-hairline rounded-[18px]" />
          <div className="h-4 w-96 bg-paper border border-hairline rounded-[6px]" />
        </div>
        <div className="h-8 w-36 bg-paper border border-hairline rounded-[18px]" />
      </div>

      {/* Hero skeleton */}
      <div className="h-72 w-full rounded-cards bg-paper border border-hairline shadow-subtle" />

      {/* Grid skeleton */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-28 rounded-cards bg-paper border border-hairline p-4 shadow-subtle" />
        ))}
      </div>

      {/* Table skeleton */}
      <div className="h-64 rounded-cards bg-paper border border-hairline shadow-subtle" />
    </div>
  );
}

