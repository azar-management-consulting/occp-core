import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        occp: {
          primary: "#2563eb",
          secondary: "#7c3aed",
          accent: "#06b6d4",
          dark: "#0f172a",
        },
      },
    },
  },
  plugins: [],
};

export default config;
