const nextJest = require('next/jest');

const createJestConfig = nextJest({ dir: './' });

/** @type {import('jest').Config} */
const config = {
  testEnvironment: 'jest-environment-jsdom',
moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  testMatch: ['**/__tests__/**/*.{ts,tsx}'],
  coverageProvider: 'v8',
  collectCoverageFrom: [
    'lib/api.ts',
    'lib/navigationGuard.tsx',
    'middleware.ts',
    'app/**/profile/page.tsx',
    'app/**/allergies/page.tsx',
    '!**/*.d.ts',
  ],
};

module.exports = createJestConfig(config);
