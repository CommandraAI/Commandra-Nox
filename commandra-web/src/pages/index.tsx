import { useLocation } from "wouter";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { MainContent, SidebarLayout } from "@/components/layout/sidebar-layout";
import { ChatInput } from "@/components/chat/chat-input";
import logoIcon from "@assets/1000043984-removebg-preview_1783780439678.png";
import { ChevronDown, Circle } from "lucide-react";
import { useCreateThread, useGetOllamaStatus } from "@workspace/api-client-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

export function IndexPage() {
  const [, setLocation] = useLocation();
  const { data: status } = useGetOllamaStatus();

  const createThread = useCreateThread();

  const handleSend = (content: string, effort: "low" | "medium" | "high", planMode: boolean) => {
    createThread.mutate(
      {
        data: {
          title: content.slice(0, 40) + (content.length > 40 ? "..." : ""),
          model: "commandra-nox",
          effort,
        },
      },
      {
        onSuccess: (thread) => {
          setLocation(
            `/threads/${thread.id}?initMsg=${encodeURIComponent(content)}&effort=${effort}&plan=${planMode}`
          );
        },
      }
    );
  };

  const isOllamaRunning = status?.running;

  return (
    <SidebarLayout>
      <AppSidebar />
      <MainContent className="bg-[#0a0a0a]">
        {/* Full center: logo + model + text + input all as one centered block */}
        <div className="flex-1 flex flex-col items-center justify-center gap-5 px-4">
          {/* Logo */}
          <img
            src={logoIcon}
            alt="Commandra"
            className="w-10 h-10 invert opacity-60"
          />

          {/* Model selector pill */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-transparent hover:bg-white/5 transition-colors text-sm">
                <Circle
                  className={`w-2 h-2 fill-current ${
                    isOllamaRunning ? "text-emerald-400" : "text-white/20"
                  }`}
                />
                <span className="text-white/60 text-xs">Commandra Nox</span>
                <ChevronDown className="w-3 h-3 text-white/20" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="center"
              className="w-48 bg-[#111] border-white/8 backdrop-blur-xl"
            >
              <DropdownMenuItem className="gap-2 cursor-pointer text-white/70 focus:text-white focus:bg-white/8">
                <Circle className="w-2 h-2 fill-current text-emerald-400" />
                <span>Commandra Nox</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled
                className="gap-2 opacity-30 cursor-not-allowed"
              >
                <Circle className="w-2 h-2 fill-current text-white/20" />
                <span>Commandra Astra</span>
                <span className="ml-auto text-[9px] text-white/30 font-mono">SOON</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled
                className="gap-2 opacity-30 cursor-not-allowed"
              >
                <Circle className="w-2 h-2 fill-current text-white/20" />
                <span>Commandra Solis</span>
                <span className="ml-auto text-[9px] text-white/30 font-mono">SOON</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Tagline */}
          <p className="text-white/25 text-sm tracking-wide">
            Are you ready to COOK?
          </p>

          {/* Input — part of the centered block, not absolute */}
          <div className="w-full max-w-2xl mt-2">
            <ChatInput onSend={handleSend} isGenerating={createThread.isPending} />
          </div>
        </div>
      </MainContent>
    </SidebarLayout>
  );
}
