import { Route, Switch, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { useState } from "react";

import { IndexPage } from '@/pages/index';
import { ThreadPage } from '@/pages/thread';
import { SettingsPage } from '@/pages/settings';
import { GithubPage } from '@/pages/github';
import NotFound from '@/pages/not-found';
import { SetupPage } from '@/pages/setup';

const queryClient = new QueryClient();

const API = import.meta.env.VITE_API_URL ?? "/api";

function AppShell() {
  const [setupDone, setSetupDone] = useState(false);

  // Check Ollama status on mount — show setup if not running
  const { data: status, isLoading } = useQuery({
    queryKey: ['ollama-boot-check'],
    queryFn: async () => {
      const res = await fetch(`${API}/ollama/status`);
      if (!res.ok) return { running: false, models: [] };
      return res.json();
    },
    staleTime: Infinity,
    retry: 2,
  });

  // Determine if setup is needed
  const ollamaRunning = status?.running === true;
  const hasModel = (status?.models ?? []).some((m: string) =>
    m.includes("qwen2.5") || m.includes("nox")
  );
  const needsSetup = !setupDone && (!ollamaRunning || !hasModel);

  // Still loading — show minimal splash
  if (isLoading) {
    return (
      <div className="h-screen w-screen bg-[#080808] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 opacity-40">
          <svg viewBox="0 0 40 40" fill="none" className="w-8 h-8 text-white animate-pulse">
            <path d="M28 32L16 20L28 8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M20 32L8 20L20 8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="text-[10px] font-mono text-white/30 tracking-widest uppercase">Loading</span>
        </div>
      </div>
    );
  }

  // Needs setup → show setup wizard
  if (needsSetup) {
    return <SetupPage onDone={() => setSetupDone(true)} />;
  }

  // Main app
  return (
    <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
      <Switch>
        <Route path="/" component={IndexPage} />
        <Route path="/threads/:id" component={ThreadPage} />
        <Route path="/settings" component={SettingsPage} />
        <Route path="/github" component={GithubPage} />
        <Route component={NotFound} />
      </Switch>
    </WouterRouter>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <AppShell />
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
