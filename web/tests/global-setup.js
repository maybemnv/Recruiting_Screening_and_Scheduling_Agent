const { spawn } = require("node:child_process");
const crypto = require("node:crypto");
const path = require("node:path");

module.exports = async () => {
  const projectRoot = path.resolve(__dirname, "../..");
  const instanceToken = crypto.randomUUID();
  const server = spawn(
    "python",
    ["-m", "apps.api", "--db", ".local/e2e.sqlite3", "--reset", "--port", "8104", "--instance-token", instanceToken],
    { cwd: projectRoot, stdio: "ignore", windowsHide: true },
  );

  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) throw new Error(`Demo server exited with ${server.exitCode}`);
    try {
      const response = await fetch("http://127.0.0.1:8104/health");
      if (response.ok) {
        const health = await response.json();
        if (health.instanceToken === instanceToken) {
          return async () => {
            if (server.exitCode === null) server.kill();
          };
        }
      }
    } catch {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  server.kill();
  throw new Error("Timed out waiting for the recruiting demo health endpoint");
};
