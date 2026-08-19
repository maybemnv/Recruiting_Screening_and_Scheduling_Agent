const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  globalSetup: require.resolve("./tests/global-setup"),
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8104",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
