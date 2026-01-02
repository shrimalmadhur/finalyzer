/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Editorial Finance palette - midnight depths with jade accents
        midnight: {
          50: '#f7f8f8',
          100: '#edefef',
          200: '#d8dcdc',
          300: '#b6bebe',
          400: '#8e9a9a',
          500: '#707e7e',
          600: '#5b6767',
          700: '#4a5454',
          800: '#404848',
          900: '#383e3e',
          950: '#0a0f0f',
        },
        jade: {
          50: '#effef7',
          100: '#dafeef',
          200: '#b8fadf',
          300: '#81f4c8',
          400: '#43e5a8',
          500: '#1acd8a',
          600: '#0fa96f',
          700: '#10855b',
          800: '#126949',
          900: '#11563d',
          950: '#033121',
        },
        cream: {
          50: '#fdfcfb',
          100: '#faf8f5',
          200: '#f5f0e8',
          300: '#ede5d7',
          400: '#dfd2bc',
          500: '#cebda0',
          600: '#bda686',
          700: '#a68d6d',
          800: '#87745b',
          900: '#6f604c',
          950: '#3b3227',
        },
        ink: {
          DEFAULT: '#0a0f0f',
          light: '#1a2020',
          lighter: '#2a3535',
        },
      },
      fontFamily: {
        display: ['var(--font-fraunces)', 'Georgia', 'serif'],
        sans: ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains)', 'monospace'],
      },
      fontSize: {
        'display-xl': ['4.5rem', { lineHeight: '1', letterSpacing: '-0.02em', fontWeight: '600' }],
        'display-lg': ['3.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '600' }],
        'display-md': ['2.5rem', { lineHeight: '1.15', letterSpacing: '-0.015em', fontWeight: '600' }],
        'display-sm': ['1.875rem', { lineHeight: '1.2', letterSpacing: '-0.01em', fontWeight: '600' }],
      },
      animation: {
        'fade-in': 'fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-up': 'fadeUp 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-down': 'fadeDown 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scaleIn 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-left': 'slideLeft 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-right': 'slideRight 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'float': 'float 6s ease-in-out infinite',
        'grain': 'grain 8s steps(10) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        slideLeft: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideRight: {
          '0%': { opacity: '0', transform: 'translateX(-20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 20px rgba(26, 205, 138, 0.3)' },
          '50%': { opacity: '0.8', boxShadow: '0 0 40px rgba(26, 205, 138, 0.5)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        grain: {
          '0%, 100%': { transform: 'translate(0, 0)' },
          '10%': { transform: 'translate(-5%, -10%)' },
          '20%': { transform: 'translate(-15%, 5%)' },
          '30%': { transform: 'translate(7%, -25%)' },
          '40%': { transform: 'translate(-5%, 25%)' },
          '50%': { transform: 'translate(-15%, 10%)' },
          '60%': { transform: 'translate(15%, 0%)' },
          '70%': { transform: 'translate(0%, 15%)' },
          '80%': { transform: 'translate(3%, 35%)' },
          '90%': { transform: 'translate(-10%, 10%)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'shimmer': 'linear-gradient(90deg, transparent 0%, rgba(26, 205, 138, 0.1) 50%, transparent 100%)',
      },
      boxShadow: {
        'glow': '0 0 40px -10px rgba(26, 205, 138, 0.4)',
        'glow-lg': '0 0 60px -15px rgba(26, 205, 138, 0.5)',
        'inner-glow': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.05)',
        'card': '0 1px 3px rgba(0, 0, 0, 0.3), 0 10px 40px -10px rgba(0, 0, 0, 0.5)',
        'card-hover': '0 1px 3px rgba(0, 0, 0, 0.3), 0 20px 60px -10px rgba(0, 0, 0, 0.6)',
      },
      borderRadius: {
        '4xl': '2rem',
        '5xl': '2.5rem',
      },
      transitionTimingFunction: {
        'out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};
