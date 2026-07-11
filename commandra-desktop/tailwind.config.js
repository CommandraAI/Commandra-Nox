/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0a0a0a',
          1: '#111111',
          2: '#1a1a1a',
          3: '#222222',
        },
        border: {
          DEFAULT: '#2a2a2a',
          subtle: '#1e1e1e',
        },
        text: {
          primary: '#e8e8e8',
          secondary: '#888888',
          muted: '#555555',
        },
        accent: {
          green: '#22c55e',
          blue: '#3b82f6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
