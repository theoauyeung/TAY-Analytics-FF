import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0F1117',
          secondary: '#161B22',
          card: '#1C2230',
          elevated: '#222B3A',
        },
        border: {
          DEFAULT: '#2D3748',
          subtle: '#222B3A',
        },
        accent: {
          DEFAULT: '#60B4FF',
          dim: '#3A7FBF',
          muted: '#1E3A5F',
        },
        text: {
          primary: '#E8EDF5',
          secondary: '#8B98A8',
          muted: '#556070',
        },
        pos: {
          qb: '#E8844A',
          rb: '#4AE8A0',
          wr: '#60B4FF',
          te: '#C47EE8',
          k:  '#E8E04A',
          dst: '#E84A4A',
        },
      },
      fontFamily: {
        display: ['system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
