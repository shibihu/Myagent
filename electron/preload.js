const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('terminalAPI', {
  sendData: (data) => ipcRenderer.send('terminal-write', data),
  onData: (callback) => ipcRenderer.on('terminal-incoming-data', (event, data) => callback(data)),
  resize: (cols, rows) => ipcRenderer.send('terminal-resize', { cols, rows }),
  setActiveWorkspace: (newWorkspacePath) => ipcRenderer.invoke('set-active-workspace', newWorkspacePath)
});
