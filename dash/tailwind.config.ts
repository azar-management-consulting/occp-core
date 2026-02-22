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
      colors: {
        occp: {
          primary: "#2563eb",
          secondary: "#7c3aed",
          accent: "#06b6d4",
          dark: "#0f172a",
          surface: "#1e293b",
          muted: "#334155",
          success: "#22c55e",
          warning: "#f59e0b",
          danger: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};

export default config;
