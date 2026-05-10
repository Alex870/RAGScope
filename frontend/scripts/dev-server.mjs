import { spawn } from "node:child_process";

const args = process.argv.slice(2);
let port = process.env.npm_config_port || process.env.PORT || "5173";
const passthrough = [];

for (let index = 0; index < args.length; index += 1) {
  const value = args[index];
  if (value === "--port" || value === "-p") {
    const next = args[index + 1];
    if (next) {
      port = next;
      index += 1;
    }
  } else if (/^\d+$/.test(value)) {
    port = value;
  } else {
    passthrough.push(value);
  }
}

const viteArgs = ["vite", "--host", "127.0.0.1", "--port", port, "--strictPort", ...passthrough];
const child = spawn("npx", viteArgs, { stdio: "inherit", shell: true });

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  }
  process.exit(code ?? 0);
});
