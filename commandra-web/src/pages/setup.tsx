import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Loader2, Download, Cpu, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import logoIcon from "@assets/1000043984-removebg-preview_1783780439678.png";

const API = import.meta.env.VITE_API_URL ?? "/api";

type Step = "detect" | "install" | "pull" | "done";

interface StepState {
  status: "pending" | "running" | "done" | "error";
  message: string;
}

async function apiFetch(path: string, method = "GET") {
  const res = await fetch(`${API}${path}`, { method });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export function SetupPage({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState<Step>("detect");
  const [steps, setSteps] = useState<Record<Step, StepState>>({
    detect: { status: "running", message: "Checking Ollama status..." },
    install: { status: "pending", message: "Install Ollama locally" },
    pull: { status: "pending", message: "Download Commandra Nox model" },
    done: { status: "pending", message: "Launch Commandra" },
  });
  const [error, setError] = useState<string | null>(null);
  const [canRetry, setCanRetry] = useState(false);

  const updateStep = (s: Step, patch: Partial<StepState>) =>
    setSteps((prev) => ({ ...prev, [s]: { ...prev[s], ...patch } }));

  // Poll Ollama until running
  const pollOllama = (): Promise<boolean> =>
    new Promise((resolve) => {
      let tries = 0;
      const id = setInterval(async () => {
        tries++;
        try {
          const data = await apiFetch("/ollama/status");
          if (data.running) {
            clearInterval(id);
            resolve(true);
          }
        } catch {}
        if (tries > 60) {
          clearInterval(id);
          resolve(false);
        }
      }, 2000);
    });

  // Pull nox model — poll until it appears in /ollama/status
  const pullModel = async (): Promise<boolean> => {
    try {
      await apiFetch("/ollama/models/nox/pull", "POST");
    } catch {}
    let tries = 0;
    while (tries < 90) {
      await new Promise((r) => setTimeout(r, 3000));
      tries++;
      try {
        const data = await apiFetch("/ollama/status");
        const models: string[] = data.models ?? [];
        if (models.some((m: string) => m.includes("qwen2.5") || m.includes("nox"))) return true;
        updateStep("pull", {
          message: `Downloading model… (this may take a few minutes)`,
        });
      } catch {}
    }
    return false;
  };

  const run = async () => {
    setError(null);
    setCanRetry(false);

    // Step 1: detect
    setStep("detect");
    updateStep("detect", { status: "running", message: "Checking Ollama status…" });
    let status: any;
    try {
      status = await apiFetch("/ollama/status");
    } catch {
      updateStep("detect", { status: "error", message: "Could not reach API server." });
      setError("API server not reachable. Try refreshing.");
      setCanRetry(true);
      return;
    }

    if (status.running) {
      updateStep("detect", { status: "done", message: "Ollama is running ✓" });
      // Check model
      const models: string[] = status.models ?? [];
      const hasNox = models.some((m: string) => m.includes("qwen2.5") || m.includes("nox"));
      if (hasNox) {
        updateStep("install", { status: "done", message: "Ollama already installed ✓" });
        updateStep("pull", { status: "done", message: "Model ready ✓" });
        setStep("done");
        updateStep("done", { status: "running", message: "Launching Commandra…" });
        setTimeout(onDone, 1200);
        return;
      }
      // Ollama running but no model — skip to pull
      updateStep("install", { status: "done", message: "Ollama already installed ✓" });
      setStep("pull");
      updateStep("pull", { status: "running", message: "Downloading Commandra Nox…" });
      const pulled = await pullModel();
      if (!pulled) {
        updateStep("pull", { status: "error", message: "Model download timed out." });
        setError("Model download timed out. Check your internet and try again.");
        setCanRetry(true);
        return;
      }
      updateStep("pull", { status: "done", message: "Model ready ✓" });
      setStep("done");
      updateStep("done", { status: "running", message: "Launching Commandra…" });
      setTimeout(onDone, 1200);
      return;
    }

    updateStep("detect", { status: "done", message: "Ollama not running — installing…" });

    // Step 2: install
    setStep("install");
    updateStep("install", { status: "running", message: "Installing Ollama…" });
    try {
      await apiFetch("/ollama/install", "POST");
    } catch {
      updateStep("install", { status: "error", message: "Install request failed." });
      setError("Failed to start Ollama installation.");
      setCanRetry(true);
      return;
    }

    updateStep("install", {
      message: "Waiting for Ollama to start… (30–60 sec on first install)",
    });
    const started = await pollOllama();
    if (!started) {
      updateStep("install", { status: "error", message: "Ollama did not start in time." });
      setError(
        "Ollama didn't start automatically. On Windows/macOS, download it from ollama.com/download, then click Retry."
      );
      setCanRetry(true);
      return;
    }
    updateStep("install", { status: "done", message: "Ollama installed & running ✓" });

    // Step 3: pull model
    setStep("pull");
    updateStep("pull", { status: "running", message: "Downloading Commandra Nox (0.5B)…" });
    const pulled = await pullModel();
    if (!pulled) {
      updateStep("pull", { status: "error", message: "Model download timed out." });
      setError("Model download timed out. Check your internet and click Retry.");
      setCanRetry(true);
      return;
    }
    updateStep("pull", { status: "done", message: "Model ready ✓" });

    // Done
    setStep("done");
    updateStep("done", { status: "running", message: "Launching Commandra…" });
    setTimeout(onDone, 1400);
  };

  useEffect(() => { run(); }, []);

  const STEPS: { key: Step; label: string }[] = [
    { key: "detect", label: "Detect Ollama" },
    { key: "install", label: "Install Ollama" },
    { key: "pull", label: "Download Nox model" },
    { key: "done", label: "Launch" },
  ];

  return (
    <div className="h-screen w-screen bg-[#080808] flex items-center justify-center px-4">
      <div className="w-full max-w-sm flex flex-col items-center gap-8">
        {/* Logo */}
        <div className="flex flex-col items-center gap-3">
          <img src={logoIcon} alt="Commandra" className="w-10 h-10 invert opacity-70" />
          <div className="text-center">
            <p className="font-mono text-xs tracking-[0.2em] text-white/30 uppercase">Commandra</p>
            <p className="text-white/60 text-sm mt-1">First-time setup</p>
          </div>
        </div>

        {/* Steps */}
        <div className="w-full flex flex-col gap-2">
          {STEPS.map(({ key, label }) => {
            const s = steps[key];
            const isActive = step === key;
            return (
              <div
                key={key}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 rounded-xl border transition-all",
                  s.status === "done"
                    ? "border-emerald-500/20 bg-emerald-500/5"
                    : s.status === "error"
                    ? "border-red-500/20 bg-red-500/5"
                    : isActive
                    ? "border-white/10 bg-white/5"
                    : "border-white/5 bg-transparent opacity-40"
                )}
              >
                <div className="shrink-0">
                  {s.status === "done" ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : s.status === "error" ? (
                    <Circle className="w-4 h-4 text-red-400 fill-current" />
                  ) : s.status === "running" ? (
                    <Loader2 className="w-4 h-4 text-white/50 animate-spin" />
                  ) : (
                    <Circle className="w-4 h-4 text-white/15" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-xs font-medium",
                    s.status === "done" ? "text-emerald-400" : s.status === "error" ? "text-red-400" : isActive ? "text-white/80" : "text-white/30"
                  )}>
                    {label}
                  </p>
                  {(isActive || s.status === "done" || s.status === "error") && (
                    <p className="text-[11px] text-white/35 mt-0.5 truncate">{s.message}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Error + retry */}
        {error && (
          <div className="w-full flex flex-col gap-3">
            <p className="text-xs text-red-400/80 text-center leading-relaxed">{error}</p>
            <div className="flex gap-2">
              {canRetry && (
                <button
                  onClick={() => run()}
                  className="flex-1 py-2.5 rounded-xl border border-white/10 bg-white/5 text-sm text-white/70 hover:bg-white/10 hover:text-white transition-colors"
                >
                  Retry
                </button>
              )}
              <a
                href="https://ollama.com/download"
                target="_blank"
                rel="noreferrer"
                className="flex-1 py-2.5 rounded-xl border border-white/10 bg-white/5 text-sm text-white/50 hover:bg-white/8 hover:text-white/80 transition-colors text-center flex items-center justify-center gap-2"
              >
                <Download className="w-3.5 h-3.5" />
                Download manually
              </a>
            </div>
          </div>
        )}

        <p className="text-[10px] text-white/20 text-center font-mono">
          LOCAL INFERENCE // NO CLOUD // NO API KEYS
        </p>
      </div>
    </div>
  );
}
