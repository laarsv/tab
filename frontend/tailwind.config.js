/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        royal: {
          DEFAULT: '#2947c9',
          soft: '#aeb9ee',
        },
        ink: '#161a24',
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
