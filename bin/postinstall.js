#!/usr/bin/env node

/**
 * postinstall script — checks for Python and required pip packages.
 * Prints warnings but never fails the install.
 */

const { execSync } = require("child_process");

const REQUIRED_PACKAGES = ["requests", "beautifulsoup4", "trafilatura", "extruct", "mcp"];

function findPython() {
  const candidates = process.platform === "win32"
    ? ["python", "python3", "py"]
    : ["python3", "python"];

  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version`, { encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"] }).trim();
      return { cmd, version };
    } catch {
      // not found, try next
    }
  }
  return null;
}

function checkPackages(pythonCmd) {
  const missing = [];
  for (const pkg of REQUIRED_PACKAGES) {
    // Map pip package names to importable module names
    const moduleMap = { beautifulsoup4: "bs4" };
    const moduleName = moduleMap[pkg] || pkg;
    try {
      execSync(`${pythonCmd} -c "import ${moduleName}"`, { stdio: ["pipe", "pipe", "pipe"] });
    } catch {
      missing.push(pkg);
    }
  }
  return missing;
}

// --- Main ---

const python = findPython();

if (!python) {
  console.log(
    "\n" +
    "  fetch-mcp: Python 3.9+ is required but was not found on PATH.\n" +
    "  Install Python from https://www.python.org/ and then run:\n" +
    `  pip install ${REQUIRED_PACKAGES.join(" ")}\n`
  );
  process.exit(0);
}

const missing = checkPackages(python.cmd);

if (missing.length > 0) {
  console.log(
    "\n" +
    `  fetch-mcp: Found ${python.version}, but missing Python dependencies:\n` +
    `  pip install ${missing.join(" ")}\n`
  );
} else {
  console.log(`\n  fetch-mcp: Ready (${python.version}, all dependencies installed)\n`);
}
