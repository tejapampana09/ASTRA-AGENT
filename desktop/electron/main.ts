import { app, BrowserWindow, ipcMain, dialog, shell } from 'electron';
import path from 'path';
import fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import http from 'http';

import net from 'net';

let mainWindow: BrowserWindow | null = null;
let pythonServerProcess: ChildProcess | null = null;

const PORT = 8765;
const BACKEND_URL = `http://127.0.0.1:${PORT}`;

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
    console.log('[Electron] ASTRA Python backend is already running on port 8765.');
    return;
  }

  console.log('[Electron] Launching ASTRA Python backend runtime...');
  const rootDir = path.resolve(__dirname, '../../');
  
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  pythonServerProcess = spawn(pythonCmd, ['-m', 'astra.server'], {
    cwd: rootDir,
    env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
    stdio: 'pipe',
  });

  pythonServerProcess.stdout?.on('data', (data) => {
    console.log(`[ASTRA Core]: ${data}`);
  });

  pythonServerProcess.stderr?.on('data', (data) => {
    console.error(`[ASTRA Core Error]: ${data}`);
  });

  pythonServerProcess.on('close', (code) => {
    console.log(`[Electron] Python backend process exited with code ${code}`);
    pythonServerProcess = null;
  });

  // Wait up to 3 seconds for backend to start
  for (let i = 0; i < 15; i++) {
    await new Promise((r) => setTimeout(r, 200));
    if (await isPortListening(PORT)) {
      console.log('[Electron] Python backend connected successfully.');
      break;
    }
  }
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
      webSecurity: false,
    },
  });

  mainWindow.setMenuBarVisibility(false);

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
    mainWindow.loadURL('http://localhost:5173');
  } else if (fs.existsSync(distIndex)) {
    console.log(`[Electron] Loading production bundle: ${distIndex}`);
    mainWindow.loadFile(distIndex);
  } else {
    console.log('[Electron] Fallback loading http://localhost:5173');
    mainWindow.loadURL('http://localhost:5173');
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

// IPC Handlers
ipcMain.handle('dialog:openDirectory', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Workspace Folder for ASTRA',
  });
  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle('shell:openPath', async (_, targetPath: string) => {
  return await shell.openPath(targetPath);
});

app.whenReady().then(async () => {
  await startPythonBackend();
  await createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
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
