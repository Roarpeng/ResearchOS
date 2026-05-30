import { spawn } from "node:child_process";
import path from "node:path";
import os from "node:os";

const cargoBin = path.join(os.homedir(), ".cargo", "bin");
const sep = process.platform === "win32" ? ";" : ":";
const pathKey = process.platform === "win32" ? "Path" : "PATH";

const env = { ...process.env };
const current = env[pathKey] ?? env.PATH ?? "";
const parts = current.split(sep).filter(Boolean);
const normalizedCargo = path.normalize(cargoBin).toLowerCase();
const hasCargo = parts.some(
  (p) => path.normalize(p).toLowerCase() === normalizedCargo,
);
if (!hasCargo) {
  env[pathKey] = `${cargoBin}${sep}${current}`;
  if (pathKey === "Path" && env.PATH !== undefined) {
    env.PATH = env.Path;
  }
}

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("with-cargo-path: missing command");
  process.exit(1);
}

const child = spawn(args[0], args.slice(1), {
  stdio: "inherit",
  env,
  shell: true,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
