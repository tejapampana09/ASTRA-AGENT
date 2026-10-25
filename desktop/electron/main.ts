import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import path from 'path';
import fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import http from 'http';
import { randomBytes } from 'crypto';

import net from 'net';
import { pathToFileURL } from 'url';

let mainWindow: BrowserWindow | null = null;
let pythonServerProcess: ChildProcess | null = null;

const PORT = 8765;
const BACKEND_URL = `http://127.0.0.1:${PORT}`;
const backendToken = process.env.ASTRA_API_TOKEN || randomBytes(32).toString('hex');
const approvedOpenRoots = new Set<string>();

function backendHealthy(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/api/health`, {
      headers: { 'X-Astra-Token': backendToken }, timeout: 2000,
    }, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        try { resolve(res.statusCode === 200 && JSON.parse(body).status === 'online'); }
        catch { resolve(false); }
      });
    });
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.on('error', () => resolve(false));
  });
}

function trustedSender(url: string): boolean {
  const bundled = path.join(__dirname, '../dist/index.html');
  try {
    const parsed = new URL(url);
    return url.split('#')[0] === pathToFileURL(bundled).href ||
      (parsed.origin === 'http://127.0.0.1:5173' || parsed.origin === 'http://localhost:5173');
  } catch { return false; }
}

function isPortListening(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const s = new net.Socket();
    s.setTimeout(600);
    s.once('connect', () => {
      s.destroy();
      resolve(true);
    });
    s.once('timeout', () => {
      s.destroy();
      resolve(false);
    });
    s.once('error', () => {
      s.destroy();
      // Try localhost (IPv6 ::1) as well
      const s2 = new net.Socket();
      s2.setTimeout(600);
      s2.once('connect', () => {
        s2.destroy();
        resolve(true);
      });
      s2.once('timeout', () => {
        s2.destroy();
        resolve(false);
      });
      s2.once('error', () => {
        s2.destroy();
        resolve(false);
      });
      s2.connect(port, 'localhost');
    });
    s.connect(port, '127.0.0.1');
  });
}

async function startPythonBackend(): Promise<void> {
  const running = await isPortListening(PORT);
  if (running) {
    if (!(await backendHealthy()) || !process.env.ASTRA_API_TOKEN) {
      throw new Error('Port 8765 is occupied. Stop that server or set its ASTRA_API_TOKEN in the desktop launch environment.');
    }
    return;
  }

  console.log('[Electron] Launching ASTRA Python backend runtime...');
  const rootDir = path.resolve(__dirname, '../../');
  
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  pythonServerProcess = spawn(pythonCmd, ['-m', 'astra.server'], {
    cwd: rootDir,
    env: { ...process.env, ASTRA_API_TOKEN: backendToken, ASTRA_REQUIRE_AUTH: 'true', ASTRA_HOST: '127.0.0.1', ASTRA_PORT: String(PORT), ASTRA_ALLOWED_ORIGINS: `${process.env.ASTRA_ALLOWED_ORIGINS || 'http://localhost:5173,http://127.0.0.1:5173,app://-'},null`, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
    stdio: 'pipe',
  });

  pythonServerProcess.stdout?.on('data', (data) => {
    console.log(`[ASTRA Core]: ${data}`);
  });

  pythonServerProcess.stderr?.on('data', (data) => {
    console.error(`[ASTRA Core Error]: ${data}`);
  });

  pythonServerProcess.on('error', (err) => { console.error('Python launch failed:', err.message); });

  pythonServerProcess.on('close', (code) => {
    console.log(`[Electron] Python backend process exited with code ${code}`);
    pythonServerProcess = null;
  });

  for (let i = 0; i < 60; i++) {
    if (await backendHealthy()) return;
    if (!pythonServerProcess) break;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('ASTRA backend did not become healthy. Check Python dependencies and configuration.');
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#121316',
    title: 'ASTRA V4 — Standalone Autonomous Software Engineering Agent',
    frame: true,
    show: true,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    },
  });

  mainWindow.webContents.session.webRequest.onBeforeSendHeaders(
    { urls: [`${BACKEND_URL}/*`, `ws://127.0.0.1:${PORT}/*`] },
    (details, callback) => {
      if (mainWindow && details.webContentsId === mainWindow.webContents.id &&
          trustedSender(mainWindow.webContents.getURL())) {
        details.requestHeaders['X-Astra-Token'] = backendToken;
      }
      callback({ requestHeaders: details.requestHeaders });
    },
  );

  mainWindow.setMenuBarVisibility(false);

  // Security: Restrict in-window navigation strictly to localhost dev server or local file bundle
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    try {
      const parsed = new URL(navigationUrl);
      const isAllowed =
        (navigationUrl.split('#')[0] === pathToFileURL(path.join(__dirname, '../dist/index.html')).href) ||
        (parsed.protocol === 'http:' && parsed.hostname === 'localhost' && parsed.port === '5173') ||
        (parsed.protocol === 'http:' && parsed.hostname === '127.0.0.1' && parsed.port === '5173');
      if (!isAllowed) {
        event.preventDefault();
        console.warn(`[Electron Security] Blocked untrusted navigation to: ${navigationUrl}`);
      }
    } catch {
      event.preventDefault();
    }
  });

  // Security: Restrict new-window creation (target="_blank" or window.open) to safe external browser links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    try {
      const parsed = new URL(url);
      if (['http:', 'https:'].includes(parsed.protocol)) {
        // Open trusted web links safely in the user's default OS browser, never in an electron webview
        shell.openExternal(url);
      }
    } catch {
      // Ignore invalid URL
    }
    return { action: 'deny' };
  });

  mainWindow.webContents.on('did-fail-load', (_, errorCode, errorDescription) => {
    console.error(`[Electron Window Load Failed]: ${errorCode} - ${errorDescription}`);
  });

  mainWindow.webContents.on('console-message', (_, level, message) => {
    console.log(`[UI Console]: ${message}`);
  });

  const distIndex = path.join(__dirname, '../dist/index.html');
  const viteUp = await isPortListening(5173);

  if (viteUp) {
    console.log('[Electron] Loading from Vite live server http://localhost:5173');
    mainWindow.loadURL('http://127.0.0.1:5173');
  } else if (fs.existsSync(distIndex)) {
    console.log(`[Electron] Loading production bundle: ${distIndex}`);
    mainWindow.loadFile(distIndex);
  } else {
    console.log('[Electron] Fallback loading http://localhost:5173');
    mainWindow.loadURL('http://127.0.0.1:5173');
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
    mainWindow?.focus();
  });

  setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
      mainWindow.focus();
    }
  }, 400);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers with validation
ipcMain.handle('dialog:openDirectory', async (event) => {
  if (!trustedSender(event.senderFrame?.url || '')) throw new Error('Untrusted IPC sender.');
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Workspace Folder for ASTRA',
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  approvedOpenRoots.add(fs.realpathSync(result.filePaths[0]));
  return result.filePaths[0];
});

function isSafeOpenPath(resolvedPath: string): boolean {
  const normalized = path.normalize(resolvedPath).toLowerCase();
  const dangerousExts = ['.exe', '.bat', '.cmd', '.ps1', '.vbs', '.msi', '.dll', '.com', '.scr', '.pif'];
  const ext = path.extname(normalized);
  if (dangerousExts.includes(ext)) {
    return false;
  }

  const parts = normalized.split(path.sep);
  const sensitiveDirs = ['.ssh', '.aws', '.gnupg', '.docker', 'windows', 'system32', 'program files', 'program files (x86)', 'etc', 'root', 'boot', 'sys', 'proc'];
  for (const part of parts) {
    if (sensitiveDirs.includes(part)) {
      return false;
    }
  }

  // Reject drive roots directly (e.g. C:\ or /)
  if (normalized === path.parse(normalized).root.toLowerCase()) {
    return false;
  }

  return true;
}

ipcMain.handle('shell:openPath', async (event, targetPath: string) => {
  if (!trustedSender(event.senderFrame?.url || '')) throw new Error('Untrusted IPC sender.');
  if (!targetPath || typeof targetPath !== 'string') {
    return 'Invalid path provided.';
  }
  const resolved = path.resolve(targetPath);
  if (!fs.existsSync(resolved)) {
    return 'Target path does not exist.';
  }
  const real = fs.realpathSync(resolved);
  const contained = [...approvedOpenRoots].some((root) => {
    const rel = path.relative(root, real);
    return rel === '' || (!rel.startsWith(`..${path.sep}`) && rel !== '..' && !path.isAbsolute(rel));
  });
  if (!contained || !isSafeOpenPath(real)) {
    console.warn(`[Electron Security] Blocked attempt to open sensitive or dangerous path: ${resolved}`);
    return 'Access denied: Target path violates security policy.';
  }
  if (fs.statSync(real).isDirectory()) return await shell.openPath(real);
  // Reveal files rather than executing an OS file association (scripts/shortcuts).
  shell.showItemInFolder(real);
  return '';
});

app.whenReady().then(async () => {
  approvedOpenRoots.add(fs.realpathSync(path.resolve(__dirname, '../../')));
  await startPythonBackend();
  await createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}).catch((error: Error) => {
  dialog.showErrorBox('ASTRA startup failed', error.message);
  app.quit();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonServerProcess) {
    console.log('[Electron] Terminating child Python runtime process...');
    pythonServerProcess.kill();
    pythonServerProcess = null;
  }
});
