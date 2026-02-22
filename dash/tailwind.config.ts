import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        pixel: ["var(--font-pixel)", "monospace"],
        mono: ["var(--font-mono)", "monospace"],
      },
      colors: {
        c64: {
          black: "#0A0A1A",
          blue: "#40318D",
          darkblue: "#161640",
          lightblue: "#7878FF",
          purple: "#B75DE5",
          cyan: "#6CE5D8",
          green: "#75CE64",
          lightgreen: "#B7FF70",
          red: "#9F4E44",
          lightred: "#D27D6F",
          yellow: "#EDF171",
          orange: "#D89555",
          brown: "#6D5412",
          white: "#FCFCFC",
          grey: "#8A8A8A",
          darkgrey: "#636363",
          lightgrey: "#ADADAD",
        },
        occp: {
          primary: "#7878FF",
          secondary: "#B75DE5",
          accent: "#6CE5D8",
          dark: "#08081e",
          surface: "#12123a",
          muted: "#2d2d6b",
          success: "#75CE64",
          warning: "#EDF171",
          danger: "#D27D6F",
        },
      },
      animation: {
        blink: "blink 1s step-end infinite",
        glow: "glow 2s ease-in-out infinite alternate",
        "pulse-slow": "pulse 3s ease-in-out infinite",
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(120, 120, 255, 0.3)" },
          "100%": { boxShadow: "0 0 20px rgba(120, 120, 255, 0.6)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
