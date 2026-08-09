const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const os = require('os');
const pty = require('node-pty');

let mainWindow;
let ptyProcess;
let activeWorkspaceDir = process.env.WORKSPACE_DIR || path.join(__dirname, '..', 'workspace');
let fsWatcher;

function startWatchingWorkspace() {
  const fs = require('fs');
  const chokidar = require('chokidar');

  if (fsWatcher) {
    try {
      fsWatcher.close();
    } catch (e) {}
  }

  if (fs.existsSync(activeWorkspaceDir)) {
    try {
      fsWatcher = chokidar.watch(activeWorkspaceDir, {
        ignored: /(^|[\/\\])\.git/, // Ignore heavy .git directories but allow other dotfiles like .github_config
        persistent: true,
        ignoreInitial: true,
        depth: 9
      });

      fsWatcher.on('all', (event, filePath) => {
        if (mainWindow) {
          mainWindow.webContents.send('workspace:disk-changed', { event, filePath });
          // Also keep workspace:file-changed for backward compatibility if needed
          const relativePath = path.relative(activeWorkspaceDir, filePath);
          mainWindow.webContents.send('workspace:file-changed', { eventType: event, filename: relativePath });
        }
      });

      console.log(`[Chokidar Watcher] Started watching directory: ${activeWorkspaceDir}`);
    } catch (e) {
      console.error(`[Chokidar Watcher] Failed to watch ${activeWorkspaceDir}:`, e);
    }
  }
}

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

  ptyProcess = pty.spawn(shell, [], {
    name: 'xterm-color',
    cols: 80,
    rows: 24,
    cwd: activeWorkspaceDir,
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
  startWatchingWorkspace();
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
    activeWorkspaceDir = resolvedPath;
    startWatchingWorkspace();

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

// Direct Disk Persistence IPC Handlers (File CRUD operations)
ipcMain.handle('fs:create-file', async (event, { filepath }) => {
  const fs = require('fs').promises;
  const targetPath = path.isAbsolute(filepath) ? filepath : path.join(activeWorkspaceDir, filepath);
  try {
    const parentDir = path.dirname(targetPath);
    await fs.mkdir(parentDir, { recursive: true });
    await fs.writeFile(targetPath, '', 'utf-8');
    return { status: 'success', message: `Created file ${filepath} successfully.` };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
});

ipcMain.handle('fs:create-folder', async (event, { folderPath }) => {
  const fs = require('fs').promises;
  const targetPath = path.isAbsolute(folderPath) ? folderPath : path.join(activeWorkspaceDir, folderPath);
  try {
    await fs.mkdir(targetPath, { recursive: true });
    return { status: 'success', message: `Created folder ${folderPath} successfully.` };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
});

ipcMain.handle('fs:save-file', async (event, { filepath, content }) => {
  const fs = require('fs').promises;
  const targetPath = path.isAbsolute(filepath) ? filepath : path.join(activeWorkspaceDir, filepath);
  try {
    const parentDir = path.dirname(targetPath);
    await fs.mkdir(parentDir, { recursive: true });
    await fs.writeFile(targetPath, content, 'utf-8');
    return { status: 'success', message: 'Saved successfully.' };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
});

ipcMain.handle('fs:read-file', async (event, { filepath }) => {
  const fs = require('fs').promises;
  const targetPath = path.isAbsolute(filepath) ? filepath : path.join(activeWorkspaceDir, filepath);
  try {
    const content = await fs.readFile(targetPath, 'utf-8');
    return { status: 'success', content };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
});

ipcMain.handle('fs:delete', async (event, { path: itemPath }) => {
  const fs = require('fs').promises;
  const targetPath = path.isAbsolute(itemPath) ? itemPath : path.join(activeWorkspaceDir, itemPath);
  try {
    await fs.rm(targetPath, { recursive: true, force: true });
    return { status: 'success', message: 'Deleted successfully.' };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
});

ipcMain.handle('fs:rename', async (event, { oldPath, newPath }) => {
  const fs = require('fs').promises;
  const targetOld = path.isAbsolute(oldPath) ? oldPath : path.join(activeWorkspaceDir, oldPath);
  const targetNew = path.isAbsolute(newPath) ? newPath : path.join(activeWorkspaceDir, newPath);
  try {
    await fs.rename(targetOld, targetNew);
    return { status: 'success', message: 'Renamed successfully.' };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
});
