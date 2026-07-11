import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Plus, Github, Settings, Trash2, ChevronLeft, ChevronRight, MessageSquare } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useAppStore } from '../store';
import { cn, timeAgo } from '../lib/utils';

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const { sidebarOpen, toggleSidebar, activeThreadId, setActiveThread } = useAppStore();

  const { data: threads = [] } = useQuery({
    queryKey: ['threads'],
    queryFn: api.threads.list,
    refetchInterval: 5000,
  });

  const deleteMutation = useMutation({
    mutationFn: api.threads.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['threads'] });
      if (activeThreadId) {
        setActiveThread(null);
        navigate('/');
      }
    },
  });

  const newThread = async () => {
    const thread = await api.threads.create({
      title: 'New thread',
      model: 'nox',
      effort: 'medium',
    });
    setActiveThread(String(thread.id));
    navigate(`/threads/${thread.id}`);
    qc.invalidateQueries({ queryKey: ['threads'] });
  };

  if (!sidebarOpen) {
    return (
      <div className="w-10 flex flex-col items-center py-3 border-r border-[#1e1e1e] gap-3">
        <button
          onClick={toggleSidebar}
          className="w-7 h-7 flex items-center justify-center rounded text-[#555] hover:text-[#888] hover:bg-[#1a1a1a]"
        >
          <ChevronRight size={14} />
        </button>
        <button
          onClick={newThread}
          className="w-7 h-7 flex items-center justify-center rounded text-[#555] hover:text-[#888] hover:bg-[#1a1a1a]"
        >
          <Plus size={14} />
        </button>
        <button
          onClick={() => navigate('/github')}
          className="w-7 h-7 flex items-center justify-center rounded text-[#555] hover:text-[#888] hover:bg-[#1a1a1a]"
        >
          <Github size={14} />
        </button>
        <button
          onClick={() => navigate('/settings')}
          className="w-7 h-7 flex items-center justify-center rounded text-[#555] hover:text-[#888] hover:bg-[#1a1a1a]"
        >
          <Settings size={14} />
        </button>
      </div>
    );
  }

  return (
    <div className="w-[220px] flex flex-col border-r border-[#1e1e1e] bg-[#0d0d0d] shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-[#1e1e1e]">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          {/* Chevron logo */}
          <div className="w-5 h-5 flex items-center justify-center">
            <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 text-[#e8e8e8]">
              <path d="M15 18L9 12L15 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M10 18L4 12L10 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="text-xs font-semibold tracking-[0.15em] text-[#e8e8e8] uppercase">Commandra</span>
        </button>
        <button
          onClick={toggleSidebar}
          className="w-6 h-6 flex items-center justify-center rounded text-[#555] hover:text-[#888] hover:bg-[#1a1a1a]"
        >
          <ChevronLeft size={13} />
        </button>
      </div>

      {/* Nav */}
      <div className="px-2 py-2 flex flex-col gap-0.5">
        <NavItem icon={<Plus size={14} />} label="New thread" onClick={newThread} />
        <NavItem
          icon={<Github size={14} />}
          label="GitHub"
          onClick={() => navigate('/github')}
          active={location.pathname === '/github'}
        />
        <NavItem
          icon={<Settings size={14} />}
          label="Settings"
          onClick={() => navigate('/settings')}
          active={location.pathname === '/settings'}
        />
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto py-2 px-2">
        {threads.length > 0 && (
          <p className="text-[10px] text-[#444] uppercase tracking-wider px-2 mb-1.5">Recent</p>
        )}
        <div className="flex flex-col gap-0.5">
          {threads.map((thread) => (
            <ThreadItem
              key={thread.id}
              thread={thread}
              active={location.pathname === `/threads/${thread.id}`}
              onClick={() => {
                setActiveThread(String(thread.id));
                navigate(`/threads/${thread.id}`);
              }}
              onDelete={() => deleteMutation.mutate(thread.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function NavItem({
  icon, label, onClick, active,
}: { icon: React.ReactNode; label: string; onClick: () => void; active?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2.5 w-full px-2.5 py-1.5 rounded text-left text-sm transition-colors',
        active
          ? 'bg-[#1a1a1a] text-[#e8e8e8]'
          : 'text-[#888] hover:text-[#ccc] hover:bg-[#161616]'
      )}
    >
      <span className="opacity-70">{icon}</span>
      {label}
    </button>
  );
}

function ThreadItem({
  thread, active, onClick, onDelete,
}: {
  thread: { id: number; title: string; messageCount: number; createdAt: string };
  active: boolean; onClick: () => void; onDelete: () => void;
}) {
  const [hovering, setHovering] = useState(false);

  return (
    <div
      className={cn(
        'group flex items-center gap-2 px-2.5 py-1.5 rounded cursor-pointer',
        active ? 'bg-[#1a1a1a] text-[#e8e8e8]' : 'text-[#666] hover:bg-[#141414] hover:text-[#bbb]'
      )}
      onClick={onClick}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <MessageSquare size={12} className="shrink-0 opacity-50" />
      <div className="flex-1 min-w-0">
        <p className="text-xs truncate leading-tight">{thread.title}</p>
        <p className="text-[10px] text-[#444] mt-0.5">{timeAgo(thread.createdAt)}</p>
      </div>
      {hovering && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="w-5 h-5 flex items-center justify-center rounded text-[#555] hover:text-red-500 hover:bg-[#1a1a1a] shrink-0"
        >
          <Trash2 size={11} />
        </button>
      )}
    </div>
  );
}
