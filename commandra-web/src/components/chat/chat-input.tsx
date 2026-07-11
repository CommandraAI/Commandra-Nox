import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Plus, Send, BrainCircuit } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (content: string, effort: "low" | "medium" | "high", planMode: boolean) => void;
  isGenerating?: boolean;
}

export function ChatInput({ onSend, isGenerating }: ChatInputProps) {
  const [content, setContent] = useState("");
  const [effort, setEffort] = useState<"low" | "medium" | "high">("medium");
  const [planMode, setPlanMode] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!content.trim() || isGenerating) return;
    onSend(content.trim(), effort, planMode);
    setContent("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [content]);

  return (
    <div className="w-full max-w-2xl mx-auto px-4">
      <div className={cn(
        "relative flex flex-col rounded-2xl border bg-[#141414] transition-all",
        "border-white/8 focus-within:border-white/15",
      )}>
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything"
          className="min-h-[44px] resize-none border-0 bg-transparent px-4 py-3.5 text-sm shadow-none focus-visible:ring-0 placeholder:text-white/20 scrollbar-none text-white/80"
          rows={1}
          disabled={isGenerating}
        />

        <div className="flex items-center px-3 pb-2.5 pt-0 gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full text-white/20 hover:text-white/50 hover:bg-transparent">
            <Plus className="h-3.5 w-3.5" />
          </Button>

          <div className="flex items-center gap-0">
            {(["low", "medium", "high"] as const).map((e) => (
              <button
                key={e}
                onClick={() => setEffort(e)}
                className={cn(
                  "px-2.5 py-1 text-[11px] font-mono rounded transition-colors capitalize",
                  effort === e
                    ? "text-white/80 font-semibold"
                    : "text-white/25 hover:text-white/50"
                )}
              >
                {e.charAt(0).toUpperCase() + e.slice(1)}
              </button>
            ))}
          </div>

          <button
            onClick={() => setPlanMode(!planMode)}
            className={cn(
              "px-2.5 py-1 text-[11px] font-mono rounded transition-colors ml-0.5",
              planMode
                ? "text-white/80 font-semibold"
                : "text-white/25 hover:text-white/50"
            )}
          >
            Plan
          </button>

          <div className="flex-1" />

          <Button
            onClick={handleSend}
            disabled={!content.trim() || isGenerating}
            size="icon"
            variant="ghost"
            className={cn(
              "h-7 w-7 rounded-full transition-all",
              content.trim() && !isGenerating
                ? "text-white/70 hover:text-white hover:bg-white/10"
                : "text-white/15 cursor-default"
            )}
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
