#!/usr/bin/env node

/**
 * npm bin wrapper for the fetch MCP server.
 *
 * Spawns the Python server script with stdio inherited so the MCP client
 * can communicate directly with the Python process.
 */

const { spawn } = require("child_process");
const path = require("path");

const serverScript = path.join(__dirname, "..", "fetch", "scripts", "server.py");

// Try python3 first, fall back to python
const pythonCandidates = process.platform === "win32"
  ? ["python", "python3", "py"]
  : ["python3", "python"];

function trySpawn(candidates) {
  const cmd = candidates[0];
  if (!cmd) {
    process.stderr.write(
      "Error: Python 3.9+ is required but no python executable was found.\n" +
      "Install Python from https://www.python.org/ and ensure it is on your PATH.\n"
    );
    process.exit(1);
  }

  const child = spawn(cmd, [serverScript], {
    stdio: "inherit",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });

  child.on("error", () => {
    // This python candidate doesn't exist, try the next one
    trySpawn(candidates.slice(1));
  });

  child.on("exit", (code) => {
    process.exit(code ?? 1);
  });
}

trySpawn(pythonCandidates);
