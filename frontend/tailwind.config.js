/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
        },
        // Banner surfaces (INTERFACE_CONTRACT §4) — tinted backgrounds for
        // full-width warning/error banners. Pairs with the semantic
        // warning/destructive tokens (which color text/icons) to replace
        // the hardcoded bg-yellow-50 / bg-red-50 pattern.
        "banner-warning": {
          bg: "hsl(var(--banner-warning-bg))",
          border: "hsl(var(--banner-warning-border))",
        },
        "banner-error": {
          bg: "hsl(var(--banner-error-bg))",
          border: "hsl(var(--banner-error-border))",
        },
      },
    },
  },
  plugins: [],
};
