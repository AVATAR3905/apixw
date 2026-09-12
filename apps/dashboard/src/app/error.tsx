"use client";

import React, { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-[55vh] flex items-center justify-center py-12">
      <div className="max-w-md w-full rounded-cards border border-hairline bg-paper p-8 text-center space-y-6 shadow-subtle">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-[18px] bg-red-50 border border-red-200 text-ember">
          <AlertTriangle className="h-7 w-7 text-ember" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-tight text-ink font-sans">
            Unable to Load Analytics View
          </h2>
          <p className="text-xs text-mid-gray leading-relaxed font-sans">
            A temporary rendering or calculation discrepancy occurred while loading this observatory module.
          </p>
          {error.message && (
            <div className="rounded-nested bg-canvas p-3 font-mono text-[11px] text-ember border border-red-200 mt-2 text-left overflow-x-auto">
              {error.message}
            </div>
          )}
        </div>

        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            onClick={() => reset()}
            className="inline-flex items-center gap-2 rounded-[18px] bg-ink px-4 py-2 text-xs font-medium text-paper hover:bg-ink-soft transition-colors shadow-subtle"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Retry Calculation
          </button>
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-[18px] border border-hairline bg-canvas px-4 py-2 text-xs font-medium text-ink hover:bg-paper hover:border-mid-gray transition-colors"
          >
            <Home className="h-3.5 w-3.5" /> Return Overview
          </Link>
        </div>
      </div>
    </div>
  );
}

