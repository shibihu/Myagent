const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let mainWindow;
let pythonProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 850,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // 1. สั่งรัน FastAPI Server (app.py) ในเครื่อง
  // (ช่วง Dev สามารถรัน python app.py หรือ uvicorn ตรงๆ ได้)
  pythonProcess = spawn('python', ['app.py']);

  pythonProcess.stdout.on('data', (data) => {
    console.log(`Python Backend: ${data}`);
  });

  // 2. ให้ Electron โหลดหน้าเว็บจาก FastAPI Local Server (เช่น http://127.0.0.1:8000)
  // หรือถ้าทำ Frontend แยกไว้ ให้ดึงไฟล์ static HTML มาเปิด
  setTimeout(() => {
    mainWindow.loadURL('http://127.0.0.1:8000'); // URL ของ FastAPI บนเครื่อง
  }, 2000); // รอให้ Python Server เริ่มทำงานประมาณ 2 วิ
}

// เมื่อปิดแอป Electron ให้ทำการฆ่า Process ของ Python เบื้องหลังด้วย
app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

app.whenReady().then(createWindow);
