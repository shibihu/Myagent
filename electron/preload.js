const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('terminalAPI', {
  sendData: (data) => ipcRenderer.send('terminal-write', data),
  onData: (callback) => ipcRenderer.on('terminal-incoming-data', (event, data) => callback(data)),
  resize: (cols, rows) => ipcRenderer.send('terminal-resize', { cols, rows }),
  setActiveWorkspace: (newWorkspacePath) => ipcRenderer.invoke('set-active-workspace', newWorkspacePath),
  createFile: (filepath) => ipcRenderer.invoke('fs:create-file', { filepath }),
  createFolder: (folderPath) => ipcRenderer.invoke('fs:create-folder', { folderPath }),
  saveFile: (filepath, content) => ipcRenderer.invoke('fs:save-file', { filepath, content }),
  readFile: (filepath) => ipcRenderer.invoke('fs:read-file', { filepath }),
  deletePath: (path) => ipcRenderer.invoke('fs:delete', { path }),
  renamePath: (oldPath, newPath) => ipcRenderer.invoke('fs:rename', { oldPath, newPath }),
  onFileChanged: (callback) => ipcRenderer.on('workspace:file-changed', (event, data) => callback(data))
});
