import { create } from 'zustand';

export type Effort = 'low' | 'medium' | 'high';

export interface Thread {
  id: string;
  title: string;
  model: string;
  effort: Effort;
  messageCount: number;
  createdAt: string;
}

export interface Message {
  id: string;
  threadId: string;
  role: 'user' | 'assistant';
  content: string;
  model?: string;
  effort?: Effort;
  planMode?: boolean;
  createdAt: string;
}

interface AppState {
  activeThreadId: string | null;
  effort: Effort;
  planMode: boolean;
  model: string;
  sidebarOpen: boolean;
  setActiveThread: (id: string | null) => void;
  setEffort: (e: Effort) => void;
  setPlanMode: (v: boolean) => void;
  setModel: (m: string) => void;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeThreadId: null,
  effort: 'medium',
  planMode: false,
  model: 'nox',
  sidebarOpen: true,
  setActiveThread: (id) => set({ activeThreadId: id }),
  setEffort: (e) => set({ effort: e }),
  setPlanMode: (v) => set({ planMode: v }),
  setModel: (m) => set({ model: m }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
