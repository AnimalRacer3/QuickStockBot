import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#07090f",
          surface: "#0d1117",
          card: "#131926",
        },
        primary: {
          DEFAULT: "#10d98a",
          hover: "#0ec07a",
          dim: "rgba(16,217,138,0.10)",
        },
        accent: {
          DEFAULT: "#4f9cf9",
          dim: "rgba(79,156,249,0.10)",
        },
        border: {
          DEFAULT: "rgba(255,255,255,0.07)",
          strong: "rgba(255,255,255,0.14)",
        },
        ink: {
          DEFAULT: "#f1f5f9",
          muted: "#8c99b0",
          subtle: "#4e5b72",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "Menlo", "monospace"],
      },
      backgroundImage: {
        "grid-dark":
          "linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "40px 40px",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(16px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s ease forwards",
        blink: "blink 1.1s step-start infinite",
      },
    },
  },
  plugins: [],
};

export default config;
