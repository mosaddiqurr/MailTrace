import { type ChildProcess, spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { createConnection } from "node:net";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HOST = "127.0.0.1";
const PORT = 8000;
const HEALTH_URL = `http://${HOST}:${PORT}/api/health`;
const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PROJECT_ROOT = resolve(FRONTEND_DIR, "..");

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

async function assertPortFree(): Promise<void> {
  await new Promise<void>((resolvePort, reject) => {
    // Windows can reject a bind while closed HTTP sockets are in TIME_WAIT.
    // Check for a live listener instead of treating those closed sockets as a server.
    const probe = createConnection({host:HOST,port:PORT});
    probe.once("connect",()=>{
      probe.destroy();
      reject(new Error(`Port ${PORT} is already in use.`));
    });
    probe.once("error",(error:NodeJS.ErrnoException)=>{
      probe.destroy();
      if(error.code==="ECONNREFUSED") resolvePort();
      else reject(error);
    });
    probe.setTimeout(2_000,()=>{
      probe.destroy();
      reject(new Error(`Could not check port ${PORT}.`));
    });
  });
}

async function waitForHealth(server: ChildProcess): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) {
      throw new Error(`MailTrace test server exited early with code ${server.exitCode}.`);
    }
    try {
      const response = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(2_000) });
      if (response.ok) return;
    } catch {
      // Expected while Uvicorn starts.
    }
    await delay(250);
  }
  throw new Error("Timed out waiting for the MailTrace test server.");
}

async function waitForExit(server: ChildProcess, milliseconds: number): Promise<boolean> {
  if (server.exitCode !== null) return true;
  return await new Promise<boolean>((resolveExit) => {
    const timer = setTimeout(() => resolveExit(false), milliseconds);
    server.once("exit", () => {
      clearTimeout(timer);
      resolveExit(true);
    });
  });
}

async function stopServer(server: ChildProcess): Promise<void> {
  if (server.exitCode === null && process.platform === "win32" && server.pid) {
    // A Windows venv launcher can outlive/exit before its interpreter child.
    // Stop only this owned process tree, before losing the launcher's PID.
    await new Promise<void>((resolveStop,reject)=>{
      const stop=spawn("taskkill.exe",["/PID",String(server.pid),"/T","/F"],{windowsHide:true,stdio:"ignore"});
      stop.once("error",reject);
      stop.once("exit",code=>{
        if(code===0 || server.exitCode!==null) resolveStop();
        else reject(new Error("Could not stop the owned MailTrace test server."));
      });
    });
  } else if (server.exitCode === null) server.kill();
  if (!(await waitForExit(server, 10_000)) && server.exitCode === null) {
    server.kill("SIGKILL");
    await waitForExit(server, 5_000);
  }
  await assertPortFree();
}

export default async function globalSetup(): Promise<() => Promise<void>> {
  await assertPortFree();

  const configuredPython = process.env.MAILTRACE_PYTHON;
  const venvPython = join(
    PROJECT_ROOT,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  const python = configuredPython || (existsSync(venvPython) ? venvPython : "python");
  const dataDir = join(PROJECT_ROOT, ".tmp", `e2e-${process.pid}-${Date.now()}`);
  mkdirSync(dataDir, { recursive: true });

  const server = spawn(python, [join(PROJECT_ROOT, "scripts", "e2e-server.py")], {
    cwd: PROJECT_ROOT,
    env: { ...process.env, MAILTRACE_DATA_DIR: dataDir },
    stdio: "inherit",
    windowsHide: true,
  });

  try {
    await waitForHealth(server);
  } catch (error) {
    await stopServer(server);
    rmSync(dataDir, { recursive: true, force: true });
    throw error;
  }

  return async () => {
    await stopServer(server);
    rmSync(dataDir, { recursive: true, force: true });
  };
}
