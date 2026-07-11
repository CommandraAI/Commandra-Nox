import { useState } from "react";
import { Link, useLocation } from "wouter";
import { Plus, Settings, Github, MessageSquare, Menu, Trash2, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import logoIcon from "@assets/1000043984-removebg-preview_1783780439678.png";
import { useListThreads, useDeleteThread, getListThreadsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  const [location] = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const queryClient = useQueryClient();
  
  const { data: threads } = useListThreads({
    query: { queryKey: getListThreadsQueryKey() }
  });
  
  const deleteThread = useDeleteThread({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListThreadsQueryKey() });
      }
    }
  });

  return (
    <div className={cn(
      "flex h-full flex-col border-r border-sidebar-border bg-sidebar shrink-0 transition-all duration-300",
      isCollapsed ? "w-[60px]" : "w-[220px]"
    )}>
      {/* Header / Logo */}
      <div className="flex h-14 items-center justify-between px-4 border-b border-sidebar-border/50">
        {!isCollapsed && (
          <Link href="/" className="flex items-center gap-2 font-mono font-bold tracking-tight text-sidebar-foreground hover:text-primary transition-colors cursor-pointer overflow-hidden">
            <img src={logoIcon} alt="Logo" className="w-5 h-5 invert opacity-90 shrink-0" />
            <span>COMMANDRA</span>
          </Link>
        )}
        {isCollapsed && (
          <Link href="/" className="flex items-center justify-center w-full cursor-pointer hover:opacity-80">
             <img src={logoIcon} alt="Logo" className="w-5 h-5 invert opacity-90 shrink-0" />
          </Link>
        )}
        <Button 
          variant="ghost" 
          size="icon" 
          className={cn("h-6 w-6 text-muted-foreground hover:text-foreground shrink-0", isCollapsed && "hidden absolute")}
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          <PanelLeftClose className="h-4 w-4" />
        </Button>
      </div>

      {isCollapsed && (
        <div className="flex justify-center mt-2">
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-6 w-6 text-muted-foreground hover:text-foreground shrink-0"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            <PanelLeftOpen className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Primary Actions */}
      <div className="flex flex-col gap-1 p-3">
        <Link href="/">
          <Button variant="secondary" className={cn("w-full h-9 text-xs font-mono font-medium shadow-none bg-accent/50 hover:bg-accent border border-white/5", isCollapsed ? "justify-center px-0" : "justify-start gap-2")}>
            <Plus className="w-3.5 h-3.5 shrink-0" />
            {!isCollapsed && "New thread"}
          </Button>
        </Link>
      </div>

      <div className="flex flex-col gap-1 px-3 pb-3">
        <Link href="/github">
          <Button variant={location === "/github" ? "secondary" : "ghost"} className={cn("w-full h-8 text-xs text-muted-foreground hover:text-foreground", isCollapsed ? "justify-center px-0" : "justify-start gap-2")}>
            <Github className="w-3.5 h-3.5 shrink-0" />
            {!isCollapsed && "GitHub"}
          </Button>
        </Link>
        <Link href="/settings">
          <Button variant={location === "/settings" ? "secondary" : "ghost"} className={cn("w-full h-8 text-xs text-muted-foreground hover:text-foreground", isCollapsed ? "justify-center px-0" : "justify-start gap-2")}>
            <Settings className="w-3.5 h-3.5 shrink-0" />
            {!isCollapsed && "Settings"}
          </Button>
        </Link>
      </div>

      {/* Threads List */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {!isCollapsed && (
          <div className="px-4 py-2 text-[10px] font-mono font-semibold uppercase tracking-wider text-muted-foreground/70">
            Recent Threads
          </div>
        )}
        <ScrollArea className="flex-1 px-2">
          <div className="flex flex-col gap-0.5 pb-4">
            {threads?.map((thread) => {
              const isActive = location === `/threads/${thread.id}`;
              return (
                <div key={thread.id} className="group flex items-center relative rounded-md">
                  <Link href={`/threads/${thread.id}`} className="flex-1">
                    <Button 
                      variant={isActive ? "secondary" : "ghost"} 
                      className={cn("w-full h-8 text-xs font-normal truncate bg-transparent data-[state=open]:bg-accent", isCollapsed ? "justify-center px-0" : "justify-start px-2")}
                    >
                      {isCollapsed ? (
                        <MessageSquare className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                      ) : (
                        <span className="truncate pr-4 opacity-80 group-hover:opacity-100 transition-opacity">
                          {thread.title || "Untitled Thread"}
                        </span>
                      )}
                    </Button>
                  </Link>
                  {!isCollapsed && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 absolute right-1 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                      onClick={(e) => {
                        e.preventDefault();
                        deleteThread.mutate({ threadId: thread.id });
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
