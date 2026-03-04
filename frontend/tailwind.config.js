/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Professional dark theme - charcoal with subtle warmth
        'soc-dark': '#1a1d23',
        'soc-darker': '#12141a',
        'soc-card': '#1e2128',
        'soc-border': '#2a2e37',
        // Primary accent - professional teal
        'soc-accent': '#0891b2',
        'soc-accent-light': '#22d3ee',
        // Status colors - refined and professional
        'soc-warning': '#d97706',
        'soc-danger': '#dc2626',
        'soc-success': '#059669',
        'soc-info': '#2563eb',
        // Text colors
        'soc-text': '#e5e7eb',
        'soc-text-muted': '#9ca3af',
      }
    },
  },
  plugins: [],
}
