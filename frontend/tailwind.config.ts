import type { Config } from "tailwindcss";
import typographyPlugin from "@tailwindcss/typography";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  plugins: [typographyPlugin],
} satisfies Config;
