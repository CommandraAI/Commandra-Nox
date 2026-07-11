import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Download, CheckCircle2, XCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import { api } from '../lib/api';
import { cn } from '../lib/utils';

const MODELS = [
  { id: 'nox', name: 'Commandra Nox', size: '0.5B', desc: 'The smallest, fastest model. Always ready.', active: true },
  { id: 'solas', name: 'Commandra Solas', size: '7B', desc: 'Balanced. Great for most coding tasks.', active: false },
  { id: 'astra', name: 'Commandra Astra', size: '14B', desc: 'High capability. Complex reasoning.', active: false },
  { id: 'solis', name: 'Commandra Solis', size: '32B', desc: 'Maximum power. Entire codebases.', active: false },
];

export default function SettingsPage() {
  const qc = useQueryClient();
  const [showToken, setShowToken] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [installMsg, setInstallMsg] = useState('');

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['ollama-status'],
    queryFn: api.ollama.status,
    refetchInterval: 5000,
  });

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: api.settings.get,
  });

  const updateMutation = useMutation({
    mutationFn: api.settings.update,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  });

  const handleInstall = async () => {
    setInstalling(true);
    setInstallMsg('');
    try {
      const res = await api.ollama.install();
      setInstallMsg(res.message);
      setTimeout(() => refetchStatus(), 3000);
    } catch {
      setInstallMsg('Failed to start installation. Visit https://ollama.com/download');
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <h1 className="text-base font-semibold text-[#e8e8e8] mb-6">Settings</h1>

        {/* AI Models */}
        <Section title="AI Model">
          <div className="grid grid-cols-2 gap-2">
            {MODELS.map((m) => (
              <ModelCard key={m.id} model={m} />
            ))}
          </div>
        </Section>

        {/* Ollama */}
        <Section title="Ollama">
          <div className="space-y-3">
            {/* Status */}
            <div className="flex items-center justify-between p-3 bg-[#0d0d0d] rounded-lg border border-[#1e1e1e]">
              <div className="flex items-center gap-2.5">
                <div className={cn(
                  'w-2 h-2 rounded-full',
                  status?.running ? 'bg-[#22c55e]' : 'bg-[#555]'
                )} />
                <span className="text-sm text-[#ccc]">
                  {status?.running ? 'Running' : status?.installed ? 'Installed, not running' : 'Not installed'}
                </span>
              </div>
              {status?.running && status?.version && (
                <span className="text-xs text-[#444]">{status.version}</span>
              )}
            </div>

            {/* Install button */}
            {!status?.running && (
              <div>
                <button
                  onClick={handleInstall}
                  disabled={installing}
                  className="w-full flex items-center justify-center gap-2.5 py-2.5 px-4 bg-[#111] border border-[#2a2a2a] rounded-lg text-sm text-[#ccc] hover:border-[#333] hover:text-[#e8e8e8] transition-colors disabled:opacity-50"
                >
                  {installing ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Download size={14} />
                  )}
                  {installing ? 'Installing...' : 'Install Ollama'}
                </button>
                <p className="text-xs text-[#444] mt-1.5 text-center">
                  Free, local, no account required
                </p>
                {installMsg && (
                  <p className="text-xs text-[#666] mt-2 text-center">{installMsg}</p>
                )}
              </div>
            )}

            {/* Ollama URL */}
            <div>
              <label className="block text-xs text-[#555] mb-1.5">Ollama URL</label>
              <input
                defaultValue={settings?.ollamaUrl ?? 'http://localhost:11434'}
                onBlur={(e) => updateMutation.mutate({ ollamaUrl: e.target.value })}
                className="w-full bg-[#0d0d0d] border border-[#1e1e1e] rounded-lg px-3 py-2 text-sm text-[#ccc] outline-none focus:border-[#333] transition-colors font-mono"
              />
            </div>
          </div>
        </Section>

        {/* GitHub */}
        <Section title="GitHub">
          <div>
            <label className="block text-xs text-[#555] mb-1.5">Personal Access Token</label>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                defaultValue={settings?.githubToken ?? ''}
                placeholder="ghp_..."
                onBlur={(e) => updateMutation.mutate({ githubToken: e.target.value || null })}
                className="w-full bg-[#0d0d0d] border border-[#1e1e1e] rounded-lg px-3 py-2 pr-9 text-sm text-[#ccc] outline-none focus:border-[#333] transition-colors font-mono"
              />
              <button
                onClick={() => setShowToken((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#444] hover:text-[#777]"
              >
                {showToken ? <EyeOff size={13} /> : <Eye size={13} />}
              </button>
            </div>
            <p className="text-xs text-[#444] mt-1.5">Used for repo detection and GitHub integration.</p>
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h2 className="text-xs font-semibold text-[#555] uppercase tracking-wider mb-3">{title}</h2>
      {children}
    </div>
  );
}

function ModelCard({ model }: { model: typeof MODELS[0] }) {
  return (
    <div className={cn(
      'p-3 rounded-lg border transition-colors',
      model.active
        ? 'border-[#2a2a2a] bg-[#111]'
        : 'border-[#1a1a1a] bg-[#0d0d0d] opacity-50'
    )}>
      <div className="flex items-start justify-between mb-1.5">
        <div>
          <p className="text-xs font-medium text-[#ccc]">{model.name}</p>
          <p className="text-[10px] text-[#444] font-mono">{model.size}</p>
        </div>
        {model.active ? (
          <span className="text-[10px] text-[#22c55e] border border-[#1a3a20] px-1.5 py-0.5 rounded">
            Active
          </span>
        ) : (
          <span className="text-[10px] text-[#333] border border-[#1e1e1e] px-1.5 py-0.5 rounded">
            Soon
          </span>
        )}
      </div>
      <p className="text-[11px] text-[#444] leading-snug">{model.desc}</p>
    </div>
  );
}
