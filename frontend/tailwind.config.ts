import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: "#6366f1",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
} satisfies Config;
