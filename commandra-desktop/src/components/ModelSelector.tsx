import { useState } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { useAppStore } from '../store';
import { cn } from '../lib/utils';

const MODELS = [
  { id: 'nox', label: 'Commandra Nox', active: true },
  { id: 'solas', label: 'Commandra Solas', active: false },
  { id: 'astra', label: 'Commandra Astra', active: false },
  { id: 'solis', label: 'Commandra Solis', active: false },
];

export default function ModelSelector() {
  const { model, setModel } = useAppStore();
  const [open, setOpen] = useState(false);
  const selected = MODELS.find((m) => m.id === model) ?? MODELS[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#2a2a2a] bg-[#111] hover:border-[#333] transition-colors text-sm"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] shrink-0" />
        <span className="text-[#ccc]">{selected.label}</span>
        <ChevronDown size={12} className="text-[#555]" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute top-full mt-1.5 left-1/2 -translate-x-1/2 z-20 min-w-[200px] bg-[#111] border border-[#2a2a2a] rounded-lg shadow-xl overflow-hidden py-1">
            {MODELS.map((m) => (
              <button
                key={m.id}
                onClick={() => {
                  if (m.active) { setModel(m.id); setOpen(false); }
                }}
                className={cn(
                  'w-full flex items-center justify-between px-3 py-2 text-sm transition-colors',
                  m.active
                    ? 'text-[#ccc] hover:bg-[#1a1a1a] cursor-pointer'
                    : 'text-[#444] cursor-not-allowed'
                )}
              >
                <div className="flex items-center gap-2.5">
                  <span className={cn(
                    'w-1.5 h-1.5 rounded-full shrink-0',
                    m.active ? 'bg-[#22c55e]' : 'bg-[#2a2a2a]'
                  )} />
                  <span>{m.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  {!m.active && (
                    <span className="text-[10px] text-[#333] border border-[#222] px-1.5 py-0.5 rounded">
                      Soon
                    </span>
                  )}
                  {m.id === model && m.active && (
                    <Check size={11} className="text-[#22c55e]" />
                  )}
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
