# COMMANDRA

> Local-first AI coding assistant. No cloud. No API keys. Just your machine, your code, and your models.

**Commandra** is a desktop AI assistant built on top of [Ollama](https://ollama.com). It runs entirely on your hardware — your conversations, your files, and your models never leave your computer.

---

## Features

- **Local AI** — Powered by Ollama. No internet required after setup.
- **Commandra Nox** — The default model (tiny, fast, always active). Solas, Astra, and Solis coming soon.
- **Plan Mode** — Activates deep reasoning before responding.
- **Effort Control** — Low / Medium / High — tune response depth per message.
- **GitHub Integration** — Point Commandra at any local Git repository. Browse files, edit them, ask about them.
- **Thread Management** — Create, switch, and delete conversation threads.
- **Auto Ollama Installer** — First-time setup with one click.

---

## Models

| Model | Size | Status |
|-------|------|--------|
| Commandra **Nox** | 0.5B | Active |
| Commandra **Solas** | 7B | Coming Soon |
| Commandra **Astra** | 14B | Coming Soon |
| Commandra **Solis** | 32B | Coming Soon |

---

## Quick Install (Windows .exe)

```bash
git clone https://github.com/your-username/commandra.git
cd commandra/commandra-desktop
npm install
npm run build:win
```

The installer will be in `commandra-desktop/release/`.

---

## Run from Source

### Prerequisites

- [Node.js 18+](https://nodejs.org)
- [Git](https://git-scm.com)
- [Ollama](https://ollama.com) (installed automatically via the app)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/commandra.git
cd commandra

# 2. Install the desktop app dependencies
cd commandra-desktop
npm install

# 3. Run in development mode
npm run dev
```

The app will open as a desktop window. On first launch, click **Install Ollama** in Settings if you haven't installed it yet.

---

## Build .exe for Windows

```bash
cd commandra-desktop
npm install
npm run build:win
```

Output: `commandra-desktop/release/Commandra Setup 1.0.0.exe`

Double-click the installer to install Commandra on any Windows machine.

---

## Build for Other Platforms

```bash
# macOS (.dmg)
npm run build:mac

# Linux (.AppImage)
npm run build:linux
```

---

## First-Time Setup

1. Launch Commandra
2. Go to **Settings**
3. Click **Install Ollama** — this downloads and installs Ollama on your machine
4. Wait for Ollama to start (green dot appears)
5. The **Commandra Nox** model will be pulled automatically
6. Start a new thread and ask anything

---

## Directory Structure

```
commandra/
├── commandra-desktop/      # Electron desktop application
│   ├── electron/           # Main process & preload
│   ├── src/                # React frontend
│   ├── assets/             # Icons and images
│   └── package.json
├── artifacts/
│   ├── commandra/          # Web preview (React + Vite)
│   └── api-server/         # Express API server
├── lib/
│   ├── api-spec/           # OpenAPI specification
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas
│   └── db/                 # Drizzle ORM schema
└── README.md
```

---

## Tech Stack

- **Frontend**: React 18, Vite, Tailwind CSS, Framer Motion
- **Desktop**: Electron 32
- **AI**: Ollama (local inference)
- **Backend**: Express 5, Drizzle ORM, PostgreSQL
- **Type Safety**: TypeScript, Zod, OpenAPI → codegen

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)

---

*Built by Heuronic*
