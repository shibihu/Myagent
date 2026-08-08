const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const os = require('os');
const pty = require('node-pty');

let mainWindow;
let ptyProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Load the running FastAPI web application (Render cloud endpoint)
  mainWindow.loadURL(`https://myagent-807h.onrender.com`).catch((err) => {
    console.error('Failed to load Render web application URL:', err);
  });

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function setupPty() {
  const shell = os.platform() === 'win32' ? 'powershell.exe' : 'bash';

  // Set default directory to workspace if exists, otherwise home dir
  const workspaceDir = process.env.WORKSPACE_DIR || path.join(__dirname, '..', 'workspace');

  ptyProcess = pty.spawn(shell, [], {
    name: 'xterm-color',
    cols: 80,
    rows: 24,
    cwd: workspaceDir,
    env: process.env
  });

  // Listen for output from the terminal and send it to the renderer process
  ptyProcess.onData((data) => {
    if (mainWindow) {
      mainWindow.webContents.send('terminal-incoming-data', data);
    }
  });
}

app.whenReady().then(() => {
  setupPty();
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

// IPC handlers to connect renderer with the node-pty process
ipcMain.on('terminal-write', (event, data) => {
  if (ptyProcess) {
    ptyProcess.write(data);
  }
});

ipcMain.on('terminal-resize', (event, { cols, rows }) => {
  if (ptyProcess) {
    ptyProcess.resize(cols, rows);
  }
});

ipcMain.handle('set-active-workspace', async (event, newWorkspacePath) => {
  const fs = require('fs');
  const resolvedPath = path.isAbsolute(newWorkspacePath)
    ? newWorkspacePath
    : path.join(__dirname, '..', newWorkspacePath);

  if (fs.existsSync(resolvedPath)) {
    if (ptyProcess) {
      try {
        ptyProcess.kill();
      } catch (e) {
        console.error('Failed to kill active PTY:', e);
      }
    }

    const shell = os.platform() === 'win32' ? 'powershell.exe' : 'bash';
    ptyProcess = pty.spawn(shell, [], {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: resolvedPath,
      env: process.env
    });

    ptyProcess.onData((data) => {
      if (mainWindow) {
        mainWindow.webContents.send('terminal-incoming-data', data);
      }
    });

    const clearCmd = os.platform() === 'win32' ? 'Clear-Host\r' : 'clear\r';
    if (mainWindow) {
      mainWindow.webContents.send('terminal-incoming-data', `\r\n\x1b[1;32m[Electron] Switched terminal workspace directory to: ${resolvedPath}\x1b[0m\r\n`);
    }
    ptyProcess.write(clearCmd);

    return { status: 'success', active_path: resolvedPath };
  } else {
    return { status: 'error', message: `Directory does not exist: ${resolvedPath}` };
  }
});
