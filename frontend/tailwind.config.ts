import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'media',
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Brand palette — Modern Korean Kitchen
        cream: {
          50: '#FDFBF6',
          100: '#FAF7F2',
          200: '#F2EBDF',
          300: '#E6DCC9',
        },
        clay: {
          900: '#1A1715',
          800: '#27211C',
          700: '#3A322A',
          600: '#5A4D40',
          500: '#7A6A58',
          400: '#A39584',
        },
        gochu: {
          // 고추장 / tomato red — primary accent
          50: '#FDECE7',
          100: '#FAD0C5',
          400: '#EA7458',
          500: '#E2553D',
          600: '#C73E27',
          700: '#A02E1B',
        },
        herb: {
          // fresh basil/scallion green — secondary
          400: '#7DA86C',
          500: '#5C8A4F',
          600: '#456A3B',
        },
        mustard: {
          // honey/curry mustard — tertiary
          400: '#F0B85C',
          500: '#E8A33D',
          600: '#C9852A',
        },
      },
      fontFamily: {
        sans: ['var(--font-pretendard)', 'Pretendard', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        display: ['var(--font-gmarket)', '"Gmarket Sans"', 'var(--font-pretendard)', 'Pretendard', 'sans-serif'],
        serif: ['"Fraunces"', 'Georgia', 'serif'],
      },
      boxShadow: {
        sticker: '0 2px 0 0 rgba(26,23,21,0.9), 0 6px 18px -4px rgba(26,23,21,0.15)',
        'sticker-hover': '0 4px 0 0 rgba(26,23,21,0.9), 0 12px 24px -6px rgba(26,23,21,0.20)',
        soft: '0 1px 2px rgba(26,23,21,0.04), 0 8px 24px -8px rgba(26,23,21,0.10)',
      },
      borderRadius: {
        chip: '14px',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-warm': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.55' },
        },
        wiggle: {
          '0%, 100%': { transform: 'rotate(-1.2deg)' },
          '50%': { transform: 'rotate(1.2deg)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.55s cubic-bezier(0.22, 1, 0.36, 1) both',
        'pulse-warm': 'pulse-warm 1.6s ease-in-out infinite',
        wiggle: 'wiggle 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
