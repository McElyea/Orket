/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'orket-dark': '#0b0e14',
        'vibe-purple': '#8a2be2',
        'engine-cyan': '#00bfff',
      },
    },
  },
  plugins: [],
}
