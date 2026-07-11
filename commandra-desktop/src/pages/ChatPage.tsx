import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Send, Plus, Loader2, ChevronDown } from 'lucide-react';
import { api } from '../lib/api';
import { useAppStore } from '../store';
import { cn } from '../lib/utils';
import MessageBubble from '../components/MessageBubble';
import ModelSelector from '../components/ModelSelector';

export default function ChatPage() {
  const { threadId } = useParams<{ threadId?: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { effort, setEffort, planMode, setPlanMode, model } = useAppStore();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const threadIdNum = threadId ? Number(threadId) : null;

  const { data: messages = [] } = useQuery({
    queryKey: ['messages', threadIdNum],
    queryFn: () => api.messages.list(threadIdNum!),
    enabled: !!threadIdNum,
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      api.messages.send(threadIdNum!, { content, effort, planMode, model }),
    onMutate: async (content) => {
      await qc.cancelQueries({ queryKey: ['messages', threadIdNum] });
      const prev = qc.getQueryData<typeof messages>(['messages', threadIdNum]) ?? [];
      const optimistic = {
        id: Date.now(), threadId: threadIdNum!, role: 'user' as const,
        content, planMode, effort, createdAt: new Date().toISOString(),
      };
      qc.setQueryData(['messages', threadIdNum], [...prev, optimistic]);
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(['messages', threadIdNum], ctx.prev);
    },
    onSuccess: (aiMsg) => {
      qc.setQueryData(['messages', threadIdNum], (prev: typeof messages) => {
        const withoutOptimistic = (prev ?? []).filter((m) => m.id !== Date.now());
        return [...withoutOptimistic, aiMsg];
      });
      qc.invalidateQueries({ queryKey: ['messages', threadIdNum] });
      qc.invalidateQueries({ queryKey: ['threads'] });
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || sendMutation.isPending) return;
    const content = input.trim();
    setInput('');

    if (!threadIdNum) {
      const thread = await api.threads.create({ title: content.slice(0, 50), model, effort });
      useAppStore.getState().setActiveThread(String(thread.id));
      navigate(`/threads/${thread.id}`);
      qc.invalidateQueries({ queryKey: ['threads'] });
      await api.messages.send(thread.id, { content, effort, planMode, model });
      qc.invalidateQueries({ queryKey: ['messages', thread.id] });
      return;
    }

    sendMutation.mutate(content);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const isEmpty = !threadIdNum || messages.length === 0;

  return (
    <div className="flex flex-col h-full">
      {/* Main area */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <EmptyState />
        ) : (
          <div className="max-w-3xl mx-auto px-6 py-8 flex flex-col gap-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {sendMutation.isPending && (
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] flex items-center justify-center shrink-0 mt-0.5">
                  <div className="w-2 h-2 bg-[#22c55e] rounded-full animate-pulse" />
                </div>
                <div className="flex items-center gap-2 text-[#555] text-sm">
                  <Loader2 size={13} className="animate-spin" />
                  Thinking...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="px-4 pb-4 pt-2 shrink-0">
        <div className="max-w-3xl mx-auto">
          <div className="bg-[#111] border border-[#2a2a2a] rounded-xl overflow-hidden focus-within:border-[#333] transition-colors">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything"
              rows={1}
              className="w-full bg-transparent px-4 pt-3.5 pb-1 text-sm text-[#e8e8e8] placeholder-[#444] resize-none outline-none leading-relaxed selectable"
              style={{ minHeight: '44px', maxHeight: '160px' }}
            />
            <div className="flex items-center px-3 pb-2 pt-1 gap-1.5">
              <button className="w-6 h-6 flex items-center justify-center rounded text-[#444] hover:text-[#777] hover:bg-[#1a1a1a]">
                <Plus size={14} />
              </button>
              <div className="flex items-center gap-0.5 mx-0.5">
                {(['low', 'medium', 'high'] as const).map((e) => (
                  <button
                    key={e}
                    onClick={() => setEffort(e)}
                    className={cn(
                      'px-2.5 py-0.5 rounded text-[11px] capitalize transition-colors',
                      effort === e
                        ? 'text-[#e8e8e8] font-semibold'
                        : 'text-[#444] hover:text-[#777]'
                    )}
                  >
                    {e.charAt(0).toUpperCase() + e.slice(1)}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setPlanMode(!planMode)}
                className={cn(
                  'px-2.5 py-0.5 rounded text-[11px] transition-colors',
                  planMode
                    ? 'text-[#e8e8e8] bg-[#1a1a1a] border border-[#333]'
                    : 'text-[#444] hover:text-[#777]'
                )}
              >
                Plan
              </button>
              <div className="flex-1" />
              <button
                onClick={handleSend}
                disabled={!input.trim() || sendMutation.isPending}
                className={cn(
                  'w-7 h-7 flex items-center justify-center rounded-lg transition-colors',
                  input.trim() && !sendMutation.isPending
                    ? 'bg-[#22c55e] text-black hover:bg-[#16a34a]'
                    : 'bg-[#1a1a1a] text-[#444]'
                )}
              >
                {sendMutation.isPending ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Send size={13} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center h-full gap-5">
      {/* Double chevron logo */}
      <div className="opacity-20">
        <svg viewBox="0 0 40 40" fill="none" className="w-10 h-10 text-[#e8e8e8]">
          <path d="M28 32L16 20L28 8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M20 32L8 20L20 8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <ModelSelector />
      <p className="text-[#444] text-sm tracking-wide">Are you ready to COOK?</p>
    </div>
  );
}
