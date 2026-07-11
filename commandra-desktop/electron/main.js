const { app, BrowserWindow, shell, ipcMain } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const { promisify } = require('util');

const execAsync = promisify(exec);
const isDev = process.env.NODE_ENV === 'development';

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0a0a0a',
    titleBarStyle: 'hiddenInset',
    frame: process.platform !== 'win32',
    icon: path.join(__dirname, '../assets/icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Remove default menu
  mainWindow.setMenuBarVisibility(false);

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// IPC: Ollama status check
ipcMain.handle('ollama:status', async () => {
  try {
    const res = await fetch('http://localhost:11434/api/tags');
    if (res.ok) {
      const data = await res.json();
      return { running: true, models: (data.models || []).map(m => m.name) };
    }
    return { running: false, models: [] };
  } catch {
    return { running: false, models: [] };
  }
});

// IPC: Install Ollama
ipcMain.handle('ollama:install', async () => {
  const platform = process.platform;
  if (platform === 'linux') {
    const proc = spawn('sh', ['-c', 'curl -fsSL https://ollama.com/install.sh | sh'], {
      detached: true,
      stdio: 'ignore',
    });
    proc.unref();
    return { success: true, message: 'Ollama installation started in background.' };
  } else if (platform === 'darwin') {
    shell.openExternal('https://ollama.com/download');
    return { success: true, message: 'Opened Ollama download page for macOS.' };
  } else if (platform === 'win32') {
    shell.openExternal('https://ollama.com/download/windows');
    return { success: true, message: 'Opened Ollama download page for Windows.' };
  }
  return { success: false, message: 'Unsupported platform.' };
});

// IPC: Pull Ollama model
ipcMain.handle('ollama:pull', async (_, modelTag) => {
  const proc = spawn('ollama', ['pull', modelTag], {
    detached: true,
    stdio: 'ignore',
  });
  proc.unref();
  return { success: true, message: `Pulling ${modelTag}...` };
});

// IPC: Open external URL
ipcMain.handle('shell:openExternal', async (_, url) => {
  shell.openExternal(url);
});
