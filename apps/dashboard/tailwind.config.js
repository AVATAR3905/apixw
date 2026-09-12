/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Phoenix Dark Cyber Theme Tokens
        canvas: "#080c14",
        paper: "#0f172a",
        "surface-alt": "#131d33",
        ink: "#f8fafc",
        "ink-soft": "#cbd5e1",
        "mid-gray": "#94a3b8",
        hairline: "#1e293b",
        ember: "#f97316",

        // Phoenix Custom Brand Palette
        phoenix: {
          50: "#fff7ed",
          100: "#ffedd5",
          200: "#fed7aa",
          300: "#fdba74",
          400: "#fb923c",
          500: "#f97316",
          600: "#ea580c",
          700: "#c2410c",
          800: "#9a3412",
          900: "#7c2d12",
          flame: "#f97316",
          amber: "#fbbf24",
          gold: "#f59e0b",
          crimson: "#ef4444",
          cyan: "#38bdf8",
        },

        // Status Indicators for safe (green), intermediate (amber), and critical (ember/red)
        safe: {
          DEFAULT: "#10b981",
          bg: "rgba(16, 185, 129, 0.12)",
          border: "rgba(16, 185, 129, 0.35)",
          text: "#34d399",
        },
        warning: {
          DEFAULT: "#f59e0b",
          bg: "rgba(245, 158, 11, 0.12)",
          border: "rgba(245, 158, 11, 0.35)",
          text: "#fbbf24",
        },
        critical: {
          DEFAULT: "#ef4444",
          bg: "rgba(239, 68, 68, 0.12)",
          border: "rgba(239, 68, 68, 0.35)",
          text: "#f87171",
        },

        // Monochromatic & Cyber Aliases
        obsidian: "#080c14",
        abyss: "#0b0f19",
        graphite: {
          DEFAULT: "#0f172a",
          hover: "#1e293b",
        },
        surface: {
          DEFAULT: "#0f172a",
          elevated: "#131d33",
          panel: "#0b0f19",
        },
        border: {
          subtle: "#1e293b",
          strong: "#334155",
        },
        steel: "#1e293b",
        silver: "#94a3b8",
        fog: "#94a3b8",
        ash: "#64748b",
        muted: "#64748b",
        cloud: "#f8fafc",
        pure: "#ffffff",
        iris: {
          gleam: "#f97316",
          pale: "#fdba74",
          deep: "#ea580c",
        },
        cyan: {
          signal: "#38bdf8",
        },
        orchid: {
          bloom: "#f43f5e",
        },
        periwinkle: "#94a3b8",
      },
      fontFamily: {
        sans: ["Geist", "Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
        "3xl": "28px",
        cards: "20px",
        small: "6px",
        badges: "18px",
        inputs: "14px",
        nested: "12px",
        buttons: "14px",
      },
      boxShadow: {
        subtle: "0 0 0 1px rgba(255, 255, 255, 0.05), 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.2)",
        "subtle-2": "0 0 0 1px rgba(255, 255, 255, 0.08)",
        card: "0 0 0 1px rgba(255, 255, 255, 0.06), 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -4px rgba(0, 0, 0, 0.3)",
        elevated: "0 0 0 1px rgba(249, 115, 22, 0.2), 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)",
        "glow-phoenix": "0 0 20px -2px rgba(249, 115, 22, 0.35)",
        "glow-cyan": "0 0 20px -2px rgba(56, 189, 248, 0.35)",
        "glow-emerald": "0 0 20px -2px rgba(16, 185, 129, 0.35)",
      },
    },
  },
  plugins: [],
};
