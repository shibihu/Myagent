const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs'); // 👈 1. เพิ่ม fs เข้ามา
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

  // Load the running FastAPI web application
  const port = process.env.PORT || 8000;
  mainWindow.loadURL(`http://localhost:${port}`).catch(() => {
    // Fallback if local FastAPI server is not started on default port yet
    mainWindow.loadURL(`http://127.0.0.1:8000`).catch((err) => {
      console.error('Failed to load FastAPI server URL:', err);
    });
  });

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function setupPty() {
  const shell = os.platform() === 'win32' ? 'powershell.exe' : 'bash';

  // Set default directory to workspace if exists, otherwise home dir
  let workspaceDir = process.env.WORKSPACE_DIR || path.join(__dirname, '..', 'workspace');

  // 👈 2. ปรับการเช็กโฟลเดอร์อย่างปลอดภัย
  try {
    if (!fs.existsSync(workspaceDir)) {
      // ถ้าไม่มี ให้ลองสร้างโฟลเดอร์ขึ้นมาใหม่
      fs.mkdirSync(workspaceDir, { recursive: true });
    }
  } catch (err) {
    console.error("Failed to create workspace directory, falling back to home dir:", err);
    // ถ้าสร้างโฟลเดอร์ไม่ได้จริงๆ ให้ถอยไปใช้ User Home Directory
    workspaceDir = os.homedir();
  }

  // 👈 3. ครอบ try-catch ตอน spawn ป้องกันแอป Crash
  try {
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
  } catch (err) {
    console.error("Failed to spawn PTY terminal:", err);
  }
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