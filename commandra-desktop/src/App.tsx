import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ChatPage from './pages/ChatPage';
import SettingsPage from './pages/SettingsPage';
import GitHubPage from './pages/GitHubPage';
import { useAppStore } from './store';
import { cn } from './lib/utils';

export default function App() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);

  return (
    <div className="flex h-screen w-screen bg-[#0a0a0a] text-[#e8e8e8] overflow-hidden">
      <Sidebar />
      <main
        className={cn(
          'flex-1 flex flex-col min-w-0 transition-all duration-200',
        )}
      >
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/threads/:threadId" element={<ChatPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/github" element={<GitHubPage />} />
        </Routes>
      </main>
    </div>
  );
}
