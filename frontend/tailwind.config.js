/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'period-pink': '#F8BBD9',
        'period-purple': '#E1BEE7',
        'period-lavender': '#D1C4E9',
        'period-mint': '#B2DFDB',
        'menstrual': '#F8BBD9',
        'follicular': '#B2DFDB',
        'ovulation': '#FFF8E1',
        'luteal': '#E1BEE7',
      },
      backgroundColor: {
        'menstrual': '#F8BBD9',
        'follicular': '#B2DFDB',
        'ovulation': '#FFF8E1',
        'luteal': '#E1BEE7',
      },
      borderColor: {
        'menstrual': '#F8BBD9',
        'follicular': '#B2DFDB',
        'ovulation': '#FFF8E1',
        'luteal': '#E1BEE7',
      },
    },
  },
  plugins: [],
}

