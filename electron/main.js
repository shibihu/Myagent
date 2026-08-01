const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const os = require('os');
const fs = require('fs');
const pty = require('node-pty');
const { spawn } = require('child_process');

let mainWindow;
let ptyProcess;
let pythonProcess = null;

// -------------------------------------------------------------
// 1. ฟังก์ชันสั่งรัน Python FastAPI Server
// -------------------------------------------------------------
function startPythonServer() {
  // ถ้ารันบน App ที่แพ็กแล้ว ให้ไปดึง app.py จาก resources, ถ้าตอน dev ให้ดึงจาก root
  const scriptPath = app.isPackaged
    ? path.join(process.resourcesPath, 'app.py')
    : path.join(__dirname, '..', 'app.py');

  // สั่งรัน Python process เบื้องหลัง
  pythonProcess = spawn('python', [scriptPath], {
    cwd: path.dirname(scriptPath),
    stdio: 'ignore',
    detached: false
  });

  console.log('Python FastAPI server process started.');
}

// -------------------------------------------------------------
// 2. ฟังก์ชันพยายามเชื่อมต่อ Server (Retry Loop)
// -------------------------------------------------------------
function loadWindowWithRetry() {
  const port = process.env.PORT || 8000;
  const targetUrl = `http://localhost:${port}`;

  if (!mainWindow) return;

  mainWindow.loadURL(targetUrl).catch(() => {
    console.log('FastAPI Server is not ready yet, retrying in 1 second...');
    // ถ้าน้ำยังไม่เดือด (Server ยังไม่พร้อม) ให้รอ 1 วินาทีแล้วลองใหม่
    setTimeout(loadWindowWithRetry, 1000);
  });
}

// -------------------------------------------------------------
// 3. ฟังก์ชันสร้างหน้าต่างหลัก (BrowserWindow)
// -------------------------------------------------------------
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

  // เรียกใช้วงรอบ Retry เพื่อโหลด URL อย่างปลอดภัย
  loadWindowWithRetry();

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

// -------------------------------------------------------------
// 4. ฟังก์ชันตั้งค่า Terminal (node-pty)
// -------------------------------------------------------------
function setupPty() {
  const shell = os.platform() === 'win32' ? 'powershell.exe' : 'bash';

  // กำหนด workspaceให้อยู่นอก app.asar ป้องกัน Error 267 บน Windows
  let workspaceDir = process.env.WORKSPACE_DIR;

  if (!workspaceDir) {
    if (app.isPackaged) {
      workspaceDir = path.join(app.getPath('userData'), 'workspace');
    } else {
      workspaceDir = path.join(__dirname, '..', 'workspace');
    }
  }

  // เช็กการมีอยู่ของโฟลเดอร์แบบปลอดภัย
  try {
    if (!fs.existsSync(workspaceDir)) {
      fs.mkdirSync(workspaceDir, { recursive: true });
    }
  } catch (err) {
    console.error("Failed to create workspace directory, falling back to home dir:", err);
    workspaceDir = os.homedir();
  }

  // รัน Terminal Process
  try {
    ptyProcess = pty.spawn(shell, [], {
      name: 'xterm-color',
      cols: 80,
      rows: 24,
      cwd: workspaceDir,
      env: process.env
    });

    ptyProcess.onData((data) => {
      if (mainWindow) {
        mainWindow.webContents.send('terminal-incoming-data', data);
      }
    });
  } catch (err) {
    console.error("Failed to spawn PTY terminal:", err);
  }
}

// -------------------------------------------------------------
// 5. Electron Lifecycle Events
// -------------------------------------------------------------
app.whenReady().then(() => {
  startPythonServer(); // 🚀 เริ่มรัน Python Server ก่อน
  setupPty();          // 💻 ตั้งค่า Terminal
  createWindow();      // 🖼️ เปิดหน้าต่างแอป

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// ปิด Process Python เมื่อปิดแอป Electron
app.on('will-quit', () => {
  if (pythonProcess) {
    console.log('Stopping Python FastAPI server...');
    pythonProcess.kill();
  }
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

// -------------------------------------------------------------
// 6. IPC Handlers
// -------------------------------------------------------------
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