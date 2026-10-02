import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}', './components/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eefaf7',
          100: '#d8f5ea',
          500: '#0f9d7a',
          600: '#0b7a61',
          900: '#0a3a2d',
        },
      },
      boxShadow: {
        soft: '0 10px 30px rgba(15, 157, 122, 0.12)',
      },
    },
  },
  plugins: [],
};

export default config;
