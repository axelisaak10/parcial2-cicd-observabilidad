module.exports = {
  testEnvironment: "node",
  testMatch: ["<rootDir>/__tests__/**/*.test.js"],
  collectCoverageFrom: ["inventory-view.js"],
  coverageThreshold: {
    global: { branches: 80, functions: 90, lines: 90, statements: 90 }
  }
};
