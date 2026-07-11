const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('commandra', {
  ollama: {
    status: () => ipcRenderer.invoke('ollama:status'),
    install: () => ipcRenderer.invoke('ollama:install'),
    pull: (modelTag) => ipcRenderer.invoke('ollama:pull', modelTag),
  },
  shell: {
    openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
  },
});
