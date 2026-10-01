import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  selectDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
  openPath: (p: string) => ipcRenderer.invoke('shell:openPath', p),
  platform: process.platform,
});
