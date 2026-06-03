// Bumps the minor part of APP_VERSION in src/version.ts: 1.1 -> 1.2 -> ... -> 1.9 -> 1.10
// Run by .github/workflows/bump-version.yml on every push to main.
import { readFileSync, writeFileSync } from "node:fs";

const FILE = "src/version.ts";
const PATTERN = /APP_VERSION\s*=\s*"(\d+)\.(\d+)"/;

const content = readFileSync(FILE, "utf8");
const match = content.match(PATTERN);
if (!match) {
  console.error(`Could not find APP_VERSION = "X.Y" in ${FILE}`);
  process.exit(1);
}

const major = Number(match[1]);
const minor = Number(match[2]) + 1;
const next = `${major}.${minor}`;

writeFileSync(FILE, content.replace(PATTERN, `APP_VERSION = "${next}"`));
console.log(`Bumped version to ${next}`);
