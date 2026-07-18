/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17201d",
        fog: "#f4f5f1",
        moss: "#174d3d",
        mint: "#d9eee5",
        ember: "#e8663d",
      },
      boxShadow: {
        lift: "0 22px 60px -30px rgba(23, 32, 29, 0.35)",
      },
    },
  },
  plugins: [],
};
