import type { Metadata } from "next";
import "./globals.css";
import { AICopilotDrawer } from "@/components/AICopilotDrawer";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "PHOENIX | Quantitative Airfare Price Index & Aviation Intelligence",
  description: "Project Phoenix: High-Frequency Algorithmic Aviation Econometrics, Route Yield Curves & Carrier Pricing Dynamics",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-canvas text-ink font-sans antialiased selection:bg-orange-500 selection:text-white min-h-screen flex flex-col">
        <Navbar />

        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>

        <AICopilotDrawer />

        <footer className="border-t border-hairline bg-paper/70 backdrop-blur-md py-6 text-xs font-mono text-mid-gray">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-orange-500 animate-pulse" />
                <span className="font-semibold text-ink tracking-wider">PHOENIX QUANT ENGINE</span>
              </div>
              <span className="text-mid-gray">·</span>
              <span className="text-mid-gray">High-Frequency Airfare Intelligence & Pricing Lab</span>
            </div>
            <div className="text-mid-gray text-[11px] font-mono">
              10 Monitored Corridors · Unpooled T+15 Anchor · Dual-Series Laspeyres Formulation
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}


