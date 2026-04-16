import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/app/**/*.{ts,tsx}',
    './src/components/**/*.{ts,tsx}',
    './src/hooks/**/*.{ts,tsx}',
    './src/lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: 'hsl(var(--bg) / <alpha-value>)',
        fg: 'hsl(var(--fg) / <alpha-value>)',
        muted: 'hsl(var(--muted) / <alpha-value>)',
        'muted-fg': 'hsl(var(--muted-fg) / <alpha-value>)',
        card: 'hsl(var(--card) / <alpha-value>)',
        'card-fg': 'hsl(var(--card-fg) / <alpha-value>)',
        border: 'hsl(var(--border) / <alpha-value>)',
        accent: 'hsl(var(--accent) / <alpha-value>)',
        'accent-fg': 'hsl(var(--accent-fg) / <alpha-value>)',
        success: 'hsl(var(--success) / <alpha-value>)',
        warning: 'hsl(var(--warning) / <alpha-value>)',
        danger: 'hsl(var(--danger) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        flashUp: {
          '0%': { backgroundColor: 'hsl(var(--danger) / 0.25)' },
          '100%': { backgroundColor: 'transparent' },
        },
        flashDown: {
          '0%': { backgroundColor: 'hsl(var(--success) / 0.25)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
      animation: {
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        'flash-up': 'flashUp 1.5s ease-out',
        'flash-down': 'flashDown 1.5s ease-out',
      },
    },
  },
  plugins: [],
};

export default config;
