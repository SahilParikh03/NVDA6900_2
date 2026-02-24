/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        'war-bg': '#0a0a0f',
        'war-card': '#12121a',
        'war-border': '#1a1a2e',
        'war-green': '#00ff88',
        'war-red': '#ff4444',
        'war-blue': '#4a9eff',
        'war-text': '#e0e0e0',
        'war-muted': '#888888',
      },
      fontFamily: {
        'sans': ['Inter', 'system-ui', 'sans-serif'],
        'mono': ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
