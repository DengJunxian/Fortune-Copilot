import { copyFileSync, cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dist = path.join(root, "dist");
const frontendDist = path.join(root, "frontend", "dist");
const worker = path.join(root, "worker", "index.js");
const hosting = path.join(root, ".openai", "hosting.json");

const enabledFlags = [
  "FINANCIAL_GRAPH", "CLIENT_PROFILE", "LIABILITY_ENGINE", "PERSISTENT_TWIN",
  "FAMILY_ENTERPRISE", "CFS", "PRODUCT_ONTOLOGY", "MONITORING",
];
const env = { ...process.env, VITE_API_BASE_URL: "" };
for (const flag of enabledFlags) env[`VITE_ENABLE_V5_${flag}`] = "true";
const build = spawnSync("npm", ["--workspace", "frontend", "run", "build"], {
  cwd: root,
  env,
  stdio: "inherit",
});
if (build.status !== 0) process.exit(build.status || 1);
for (const file of [path.join(frontendDist, "index.html"), worker, hosting]) {
  if (!existsSync(file)) throw new Error(`Missing Sites build input: ${file}`);
}
rmSync(dist, { recursive: true, force: true });
mkdirSync(path.join(dist, "server"), { recursive: true });
mkdirSync(path.join(dist, ".openai"), { recursive: true });
cpSync(frontendDist, path.join(dist, "client"), { recursive: true });
copyFileSync(worker, path.join(dist, "server", "index.js"));
copyFileSync(hosting, path.join(dist, ".openai", "hosting.json"));
console.log("Sites artifact ready: dist/client, dist/server, dist/.openai");
