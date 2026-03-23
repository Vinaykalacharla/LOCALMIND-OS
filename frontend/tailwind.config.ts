import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        slateBg: "#0f172a",
        slateCard: "#111827",
        ink: "#e5e7eb",
        accent: "#14b8a6",
        accentSoft: "#0f766e"
      },
      boxShadow: {
        panel: "0 10px 35px rgba(0,0,0,0.28)"
      }
    }
  },
  plugins: []
};

export default config;

