import { useEffect, useRef, useState } from "react";
import { useRoute, useSearch } from "wouter";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { MainContent, SidebarLayout } from "@/components/layout/sidebar-layout";
import { ChatInput } from "@/components/chat/chat-input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  useGetThread,
  useListMessages,
  useSendMessage,
  getGetThreadQueryKey,
  getListMessagesQueryKey,
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Circle } from "lucide-react";
import { cn } from "@/lib/utils";

function MessageBubble({
  role,
  content,
  isGenerating,
}: {
  role: "user" | "assistant";
  content: string;
  isGenerating?: boolean;
}) {
  const isUser = role === "user";

  return (
    <div className={cn("flex w-full py-3", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%]",
          isUser
            ? "px-4 py-2.5 rounded-2xl rounded-tr-sm bg-[#1c1c1c] border border-white/6 text-white/80 text-sm leading-relaxed"
            : "text-white/70 text-sm leading-relaxed"
        )}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{content}</div>
        ) : content ? (
          <div className="prose prose-invert prose-sm prose-p:text-white/70 prose-pre:bg-[#111] prose-pre:border prose-pre:border-white/8 max-w-none">
            <div style={{ whiteSpace: "pre-wrap" }}>{content}</div>
          </div>
        ) : isGenerating ? (
          <div className="flex items-center gap-1.5 h-5 pt-1">
            <span
              className="w-1.5 h-1.5 rounded-full bg-emerald-400/60 animate-bounce"
              style={{ animationDelay: "0ms" }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-emerald-400/60 animate-bounce"
              style={{ animationDelay: "150ms" }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-emerald-400/60 animate-bounce"
              style={{ animationDelay: "300ms" }}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ThreadPage() {
  const [, params] = useRoute("/threads/:id");
  const threadId = parseInt(params?.id || "0", 10);
  const searchString = useSearch();
  const searchParams = new URLSearchParams(searchString);
  const [isGenerating, setIsGenerating] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const initSent = useRef(false);

  const queryClient = useQueryClient();

  const { data: thread } = useGetThread(threadId, {
    query: { enabled: !!threadId, queryKey: getGetThreadQueryKey(threadId) },
  });

  const { data: messages } = useListMessages(threadId, {
    query: { enabled: !!threadId, queryKey: getListMessagesQueryKey(threadId) },
  });

  const sendMessage = useSendMessage({
    mutation: {
      onMutate: () => setIsGenerating(true),
      onSuccess: () => {
        setIsGenerating(false);
        queryClient.invalidateQueries({ queryKey: getListMessagesQueryKey(threadId) });
        queryClient.invalidateQueries({ queryKey: ["threads"] });
      },
      onError: () => setIsGenerating(false),
    },
  });

  // Send initial message from URL param (new thread from home)
  useEffect(() => {
    const initMsg = searchParams.get("initMsg");
    if (initMsg && messages?.length === 0 && !isGenerating && !initSent.current) {
      initSent.current = true;
      const effort = (searchParams.get("effort") as any) || "medium";
      const planMode = searchParams.get("plan") === "true";
      window.history.replaceState({}, "", `/threads/${threadId}`);
      sendMessage.mutate({
        threadId,
        data: { content: initMsg, effort, planMode, model: thread?.model },
      });
    }
  }, [threadId, messages?.length]);

  // Scroll to bottom on new message
  useEffect(() => {
    if (scrollRef.current) {
      const viewport = scrollRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (viewport) viewport.scrollTop = viewport.scrollHeight;
    }
  }, [messages, isGenerating]);

  const handleSend = (
    content: string,
    effort: "low" | "medium" | "high",
    planMode: boolean
  ) => {
    sendMessage.mutate({
      threadId,
      data: { content, effort, planMode, model: thread?.model },
    });
  };

  return (
    <SidebarLayout>
      <AppSidebar />
      <MainContent className="bg-[#0a0a0a]">
        {/* Thread header */}
        <div className="h-12 border-b border-white/5 flex items-center px-5 shrink-0">
          <span className="text-sm text-white/50 truncate">{thread?.title}</span>
          <div className="ml-3 flex items-center gap-1.5 shrink-0">
            <Circle className="w-1.5 h-1.5 fill-current text-emerald-400" />
            <span className="text-[10px] font-mono text-white/25">
              {thread?.model || "nox"}
            </span>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1" ref={scrollRef}>
          <div className="max-w-2xl mx-auto px-5 py-6 flex flex-col">
            {messages?.map((msg) => (
              <MessageBubble key={msg.id} role={msg.role} content={msg.content} />
            ))}
            {isGenerating && (
              <MessageBubble role="assistant" content="" isGenerating={true} />
            )}
          </div>
        </ScrollArea>

        {/* Input */}
        <div className="shrink-0 pb-5 pt-3 bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a]/90 to-transparent">
          <ChatInput onSend={handleSend} isGenerating={isGenerating} />
        </div>
      </MainContent>
    </SidebarLayout>
  );
}
