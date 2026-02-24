/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        base: '#0A0A0F',
        surface: 'rgba(255,255,255,0.04)',
        'surface-hover': 'rgba(255,255,255,0.07)',
        'nvda-green': '#76B900',
        'green-glow': 'rgba(118,185,0,0.25)',
        'green-dim': 'rgba(118,185,0,0.12)',
        red: '#FF3B3B',
        amber: '#FFB800',
        'text-primary': '#E8E8EC',
        'text-muted': '#6B6B7B',
        border: 'rgba(118,185,0,0.10)',
        'border-hover': 'rgba(118,185,0,0.25)',
      },
      fontFamily: {
        display: ['Orbitron', 'Rajdhani', 'sans-serif'],
        body: ['Exo 2', 'Geist Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        panel: '16px',
      },
      backdropBlur: {
        glass: '16px',
      },
      boxShadow: {
        glass: '0 0 0 1px rgba(118,185,0,0.05) inset, 0 8px 32px rgba(0,0,0,0.4)',
        'glass-hover': '0 0 0 1px rgba(118,185,0,0.08) inset, 0 0 20px rgba(118,185,0,0.06), 0 8px 32px rgba(0,0,0,0.4)',
        'glass-glow': '0 0 30px rgba(118,185,0,0.15), 0 8px 32px rgba(0,0,0,0.4)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'scale(0.97)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(100%)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideOutRight: {
          '0%': { opacity: '1', transform: 'translateX(0)' },
          '100%': { opacity: '0', transform: 'translateX(100%)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(118,185,0,0.15)' },
          '50%': { boxShadow: '0 0 20px rgba(118,185,0,0.3)' },
        },
        priceTick: {
          '0%': { opacity: '1' },
          '50%': { opacity: '0.6' },
          '100%': { opacity: '1' },
        },
        crossfadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        crossfadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 400ms ease-out forwards',
        'slide-in-right': 'slideInRight 300ms ease-out forwards',
        'slide-out-right': 'slideOutRight 300ms ease-in forwards',
        shimmer: 'shimmer 2s linear infinite',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'price-tick': 'priceTick 600ms ease-in-out',
        'crossfade-in': 'crossfadeIn 250ms ease-out forwards',
        'crossfade-out': 'crossfadeOut 250ms ease-in forwards',
      },
    },
  },
  plugins: [],
}
