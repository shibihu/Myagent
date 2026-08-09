const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');
const pty = require('node-pty');
const { spawn } = require('child_process');

let mainWindow;
let ptyProcess;
let backendProcess;
let activeWorkspaceDir = process.env.WORKSPACE_DIR || path.join(__dirname, '..', 'workspace');
let fsWatcher;

// Configuration for backend
const BACKEND_PORT = 5000;
const BACKEND_HOST = '127.0.0.1';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const HEALTH_CHECK_TIMEOUT = 30000; // 30 seconds max wait
const HEALTH_CHECK_INTERVAL = 500; // Poll every 500ms

// Kills any existing process on the backend port (Windows only)
async function killProcessOnPort() {
  return new Promise((resolve) => {
    if (os.platform() !== 'win32') {
      resolve();
      return;
    }
    
    console.log(`[Backend] Attempting to free port ${BACKEND_PORT}...`);
    
    const { exec } = require('child_process');
    // Use a more robust approach with PowerShell
    const cmd = `Get-NetTCPConnection -LocalPort ${BACKEND_PORT} -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }`;
    
    exec(`powershell -Command "${cmd}"`, (err) => {
      // Don't care about errors, just move forward
      setTimeout(resolve, 1000);
    });
  });
}

// Spawns the FastAPI backend process
function spawnBackendProcess() {
  return new Promise(async (resolve, reject) => {
    try {
      // Clean up any existing process on the port first
      await killProcessOnPort();
      
      console.log('[Backend] Spawning FastAPI server...');
      
      const pythonExe = os.platform() === 'win32' ? 'python' : 'python3';
      
      // Use uvicorn to run the FastAPI app
      backendProcess = spawn(pythonExe, ['-m', 'uvicorn', 'app:app', '--host', BACKEND_HOST, '--port', BACKEND_PORT.toString(), '--log-level', 'info'], {
        cwd: path.join(__dirname, '..'),
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1'
        },
        stdio: 'pipe'
      });

      backendProcess.stdout.on('data', (data) => {
        console.log(`[FastAPI] ${data.toString().trim()}`);
      });

      backendProcess.stderr.on('data', (data) => {
        console.error(`[FastAPI Error] ${data.toString().trim()}`);
      });

      backendProcess.on('error', (err) => {
        console.error('[Backend] Failed to spawn process:', err);
        reject(err);
      });

      backendProcess.on('exit', (code) => {
        console.log(`[Backend] Process exited with code ${code}`);
        if (mainWindow) {
          mainWindow.webContents.send('backend:disconnected', { code });
        }
      });

      // Give backend a moment to start before polling
      setTimeout(() => {
        pollBackendHealth(resolve, reject);
      }, 1500);
    } catch (err) {
      reject(err);
    }
  });
}

// Polls the /health endpoint until backend is ready
function pollBackendHealth(resolve, reject, elapsed = 0) {
  const http = require('http');
  
  const healthCheckReq = http.get(`${BACKEND_URL}/health`, (res) => {
    if (res.statusCode === 200) {
      console.log('[Backend] Health check passed - backend is ready!');
      resolve();
      return;
    }
    scheduleNextPoll(resolve, reject, elapsed);
  });

  healthCheckReq.on('error', () => {
    scheduleNextPoll(resolve, reject, elapsed);
  });

  healthCheckReq.setTimeout(2000, () => {
    healthCheckReq.destroy();
    scheduleNextPoll(resolve, reject, elapsed);
  });
}

function scheduleNextPoll(resolve, reject, elapsed) {
  const newElapsed = elapsed + HEALTH_CHECK_INTERVAL;
  
  if (newElapsed > HEALTH_CHECK_TIMEOUT) {
    const err = new Error(`Backend health check failed after ${HEALTH_CHECK_TIMEOUT / 1000}s`);
    console.error('[Backend]', err.message);
    reject(err);
    return;
  }

  setTimeout(() => {
    pollBackendHealth(resolve, reject, newElapsed);
  }, HEALTH_CHECK_INTERVAL);
}

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

function buildFsTreeRecursive(dirPath, basePath) {
  const fs = require('fs');
  const name = dirPath === basePath ? 'root' : path.basename(dirPath);
  let relPath = path.relative(basePath, dirPath).replace(/\\/g, '/');
  if (relPath === '.') relPath = '';

  const stat = fs.statSync(dirPath);
  const isDir = stat.isDirectory();
  const node = { name, path: relPath, isDirectory: isDir };

  if (isDir) {
    let entries = [];
    try {
      entries = fs.readdirSync(dirPath);
    } catch (e) {
      entries = [];
    }

    const children = [];
    for (const entry of entries.sort()) {
      if (
        entry.startsWith('.') ||
        entry === '__pycache__' ||
        entry === 'node_modules' ||
        entry === '.github_config.json' ||
        entry.endsWith('.tmp')
      ) {
        continue;
      }
      children.push(buildFsTreeRecursive(path.join(dirPath, entry), basePath));
    }
    node.children = children;
  }

  return node;
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

  // Always load the page through the locally-spawned FastAPI backend so Jinja2
  // template variables (window.NEXT_PUBLIC_*, etc.) actually get rendered and
  // relative /api & /static URLs resolve correctly.
  //
  // IMPORTANT: templates/index.html is a server-side Jinja2 template (note the
  // {{ ... }} placeholders and {% raw %} tags near the top). Loading it directly
  // off disk via loadFile() uses the file:// protocol, which skips Jinja2
  // rendering entirely. That leaves the literal '{% raw %}' text sitting inside
  // the <script type="text/babel"> block, which Babel cannot parse -- so the React
  // app never mounts and the page is stuck on the static "Loading..." placeholder
  // forever. It also breaks every relative fetch('/api/...') call since there's
  // no HTTP origin under file://. Always go through the real backend instead.
  mainWindow.loadURL(BACKEND_URL).catch((err) => {
    console.error('[Electron] Failed to load local backend UI, falling back to remote:', err);
    mainWindow.loadURL('https://myagent-807h.onrender.com').catch((fallbackErr) => {
      console.error('[Electron] Failed to load Render web application URL:', fallbackErr);
    });
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

app.whenReady().then(async () => {
  try {
    // Spawn the FastAPI backend and wait for it to be ready
    await spawnBackendProcess();
    console.log('[Electron] Backend is ready, initializing UI...');
  } catch (err) {
    console.error('[Electron] Backend initialization failed:', err.message);
    // Continue anyway - frontend will show connection error
  }

  setupPty();
  startWatchingWorkspace();
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  // Clean up backend process on exit
  if (backendProcess) {
    console.log('[Backend] Terminating backend process...');
    try {
      backendProcess.kill();
    } catch (e) {
      console.error('[Backend] Error killing process:', e);
    }
  }
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
ipcMain.handle('fs:list-files', async () => {
  const fs = require('fs');
  try {
    if (!fs.existsSync(activeWorkspaceDir)) {
      return {
        status: 'success',
        files: [],
        tree: { name: 'root', path: '', isDirectory: true, children: [] }
      };
    }

    const filesList = [];
    const walk = (dir) => {
      let entries = [];
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch (e) {
        return;
      }
      for (const entry of entries) {
        if (entry.name.startsWith('.') || entry.name === '__pycache__' || entry.name === 'node_modules') {
          continue;
        }
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(fullPath);
        } else {
          if (entry.name.endsWith('.tmp') || entry.name === '.github_config.json') {
            continue;
          }
          const relPath = path.relative(activeWorkspaceDir, fullPath).replace(/\\/g, '/');
          filesList.push(relPath);
        }
      }
    };
    walk(activeWorkspaceDir);
    filesList.sort();

    const tree = buildFsTreeRecursive(activeWorkspaceDir, activeWorkspaceDir);

    return { status: 'success', files: filesList, tree };
  } catch (err) {
    return { status: 'error', message: err.message };
  }
});

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
