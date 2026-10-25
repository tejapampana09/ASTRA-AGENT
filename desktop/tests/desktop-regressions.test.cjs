const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const ts = require('typescript');

function loadSource(relative, overrides = {}) {
  const filename = path.resolve(__dirname, '..', relative);
  const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, require, __dirname: path.dirname(filename), process,
    console, URL, setTimeout, clearTimeout, ...overrides }, { filename });
  return exports;
}

function apiFixture() {
  const sockets = [];
  class Socket {
    constructor(url) { this.url = url; sockets.push(this); }
  }
  const { api } = loadSource('src/api.ts', { WebSocket: Socket });
  return { api, sockets };
}

test('task connection is scoped and waits for server subscription acknowledgement', async () => {
  const { api, sockets } = apiFixture();
  const events = [];
  api.connectWebSocket((event) => events.push(event), () => {}, 'session A');
  assert.equal(sockets[0].url, 'ws://127.0.0.1:8765/ws/events?session_id=session%20A');
  let ready = false;
  const waiting = api.waitForSessionConnection('session A').then(() => { ready = true; });
  sockets[0].onopen();
  await Promise.resolve();
  assert.equal(ready, false);
  sockets[0].onmessage({ data: JSON.stringify({ event_type: 'connection_established' }) });
  await waiting;
  assert.equal(ready, true);
  sockets[0].onmessage({ data: 'pong' });
  assert.equal(events.length, 1);
});

test('closed sockets cannot make the next task look connected', async () => {
  const { api, sockets } = apiFixture();
  api.connectWebSocket(() => {}, () => {}, 's');
  sockets[0].onmessage({ data: JSON.stringify({ event_type: 'connection_established' }) });
  await api.waitForSessionConnection('s');
  sockets[0].onclose();
  let ready = false;
  const waiting = api.waitForSessionConnection('s').then(() => { ready = true; });
  await Promise.resolve();
  assert.equal(ready, false);
  api.connectWebSocket(() => {}, () => {}, 's');
  sockets[1].onmessage({ data: JSON.stringify({ event_type: 'connection_established' }) });
  await waiting;
});

test('Electron IPC rejects untrusted senders and paths outside user-selected roots', async () => {
  const handlers = new Map();
  const opened = [], revealed = [];
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'astra-ipc-'));
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'astra-outside-'));
  const electron = {
    app: { whenReady: () => ({ then: () => ({ catch: () => {} }) }), on: () => {} },
    ipcMain: { handle: (name, handler) => handlers.set(name, handler) },
    dialog: { showOpenDialog: async () => ({ canceled: false, filePaths: [root] }) },
    shell: { openPath: async (p) => { opened.push(p); return ''; }, showItemInFolder: (p) => revealed.push(p) },
  };
  // Provide a window only for the directory picker; startup stays disabled in this isolated VM.
  let source = fs.readFileSync(path.resolve(__dirname, '../electron/main.ts'), 'utf8');
  source = source.replace('let mainWindow: BrowserWindow | null = null;', 'let mainWindow: any = {};');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  vm.runInNewContext(code, {
    exports: {}, __dirname: path.resolve(__dirname, '../dist-electron'), process, console, URL,
    setTimeout, clearTimeout, require: (name) => name === 'electron' ? electron : require(name),
  });
  const trusted = { senderFrame: { url: 'http://127.0.0.1:5173/' } };
  try {
    await assert.rejects(handlers.get('shell:openPath')({ senderFrame: { url: 'https://evil.example/' } }, root), /Untrusted/);
    await handlers.get('dialog:openDirectory')(trusted);
    assert.match(await handlers.get('shell:openPath')(trusted, outside), /Access denied/);
    await handlers.get('shell:openPath')(trusted, root);
    assert.deepEqual(opened, [root]);
    const script = path.join(root, 'program.py');
    fs.writeFileSync(script, 'raise SystemExit(1)');
    await handlers.get('shell:openPath')(trusted, script);
    assert.deepEqual(revealed, [script]);
    assert.equal(opened.length, 1, 'source files must be revealed, not executed');
    const executable = path.join(root, 'program.exe');
    fs.writeFileSync(executable, '');
    assert.match(await handlers.get('shell:openPath')(trusted, executable), /Access denied/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
    fs.rmSync(outside, { recursive: true, force: true });
  }
});
