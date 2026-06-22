/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        mint: {
          DEFAULT: '#00a984',
          soft: '#86c8af',
        },
        ink: '#1d1d1b',
        paper: '#ffffff',
      },
      fontFamily: {
        sans: ['Roboto', 'system-ui', 'sans-serif'],
      },
      letterSpacing: {
        wordmark: '-0.02em',
        tagline: '0.18em',
      },
    },
  },
  plugins: [],
};
