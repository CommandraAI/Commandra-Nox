import { AppSidebar } from "@/components/layout/app-sidebar";
import { MainContent, SidebarLayout } from "@/components/layout/sidebar-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { 
  useGetSettings, 
  useUpdateSettings,
  useGetOllamaStatus,
  useInstallOllama,
  getGetSettingsQueryKey,
  getGetOllamaStatusQueryKey
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Download, CheckCircle2, XCircle, HardDrive, Cpu, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [githubToken, setGithubToken] = useState("");

  const { data: settings } = useGetSettings({
    query: { queryKey: getGetSettingsQueryKey() }
  });

  const { data: ollamaStatus } = useGetOllamaStatus({
    query: { queryKey: getGetOllamaStatusQueryKey(), refetchInterval: 5000 } // Poll status
  });

  const updateSettings = useUpdateSettings({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetSettingsQueryKey() });
        toast({ title: "Settings saved" });
      }
    }
  });

  const installOllama = useInstallOllama({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getGetOllamaStatusQueryKey() });
        toast({ title: "Ollama installation triggered" });
      }
    }
  });

  useEffect(() => {
    if (settings) {
      setOllamaUrl(settings.ollamaUrl || "");
      setGithubToken(settings.githubToken || "");
    }
  }, [settings]);

  const handleSave = () => {
    updateSettings.mutate({
      data: {
        ollamaUrl,
        githubToken: githubToken || null
      }
    });
  };

  return (
    <SidebarLayout>
      <AppSidebar />
      <MainContent className="bg-background">
        <div className="h-14 border-b border-white/5 flex items-center px-6">
          <h1 className="font-semibold text-lg">Settings</h1>
        </div>
        
        <div className="flex-1 overflow-auto p-6 lg:p-10">
          <div className="max-w-4xl mx-auto space-y-10">
            
            {/* AI Models Section */}
            <section className="space-y-4">
              <div>
                <h2 className="text-xl font-bold tracking-tight">AI Models</h2>
                <p className="text-sm text-muted-foreground">Select your primary inference engine.</p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="border-primary/50 bg-primary/5 shadow-[0_0_15px_rgba(34,197,94,0.05)] relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-3">
                    <CheckCircle2 className="w-5 h-5 text-primary" />
                  </div>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Cpu className="w-5 h-5" />
                      Commandra Nox
                    </CardTitle>
                    <CardDescription>Fast, capable 8B model for everyday coding tasks.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="text-xs font-mono text-muted-foreground">
                      Running locally via Ollama
                    </div>
                  </CardContent>
                </Card>

                <Card className="opacity-40 grayscale cursor-not-allowed relative overflow-hidden">
                  <div className="absolute top-3 right-3 text-[10px] font-mono uppercase bg-muted px-2 py-0.5 rounded text-muted-foreground border">
                    Coming Soon
                  </div>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <HardDrive className="w-5 h-5" />
                      Commandra Astra
                    </CardTitle>
                    <CardDescription>14B model for complex reasoning tasks.</CardDescription>
                  </CardHeader>
                </Card>
              </div>
            </section>

            {/* Ollama Status Section */}
            <section className="space-y-4">
              <div>
                <h2 className="text-xl font-bold tracking-tight">Ollama Runtime</h2>
                <p className="text-sm text-muted-foreground">Manage your local inference engine connection.</p>
              </div>
              
              <Card className="bg-[#111]">
                <CardContent className="p-6">
                  <div className="flex flex-col md:flex-row gap-6 items-start md:items-center justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">Status:</span>
                        {ollamaStatus?.running ? (
                          <span className="flex items-center gap-1.5 text-primary font-mono text-sm">
                            <span className="relative flex h-2.5 w-2.5">
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary"></span>
                            </span>
                            Running
                          </span>
                        ) : (
                          <span className="flex items-center gap-1.5 text-destructive font-mono text-sm">
                            <span className="relative flex h-2 w-2">
                              <span className="relative inline-flex rounded-full h-2 w-2 bg-destructive"></span>
                            </span>
                            Not Running
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {ollamaStatus?.installed ? `Ollama installed (v${ollamaStatus.version || 'unknown'})` : 'Ollama is not installed on this system.'}
                      </div>
                    </div>

                    {!ollamaStatus?.installed && (
                      <Button 
                        onClick={() => installOllama.mutate()}
                        disabled={installOllama.isPending}
                        className="gap-2"
                      >
                        {installOllama.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        Install Ollama
                      </Button>
                    )}
                  </div>

                  <div className="mt-6 pt-6 border-t border-white/5 space-y-4">
                    <div className="space-y-2">
                      <Label>Ollama API URL</Label>
                      <div className="flex gap-2">
                        <Input 
                          value={ollamaUrl} 
                          onChange={(e) => setOllamaUrl(e.target.value)}
                          className="font-mono text-sm max-w-md bg-black/50" 
                        />
                        <Button variant="secondary" onClick={handleSave}>Save</Button>
                      </div>
                      <p className="text-xs text-muted-foreground">Default: http://localhost:11434</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </section>

            {/* GitHub Section */}
            <section className="space-y-4">
              <div>
                <h2 className="text-xl font-bold tracking-tight">Integrations</h2>
                <p className="text-sm text-muted-foreground">Connect external services.</p>
              </div>
              
              <Card className="bg-[#111]">
                <CardContent className="p-6 space-y-4">
                  <div className="space-y-2">
                    <Label>GitHub Personal Access Token</Label>
                    <div className="flex gap-2">
                      <Input 
                        type="password"
                        value={githubToken} 
                        onChange={(e) => setGithubToken(e.target.value)}
                        placeholder="ghp_..."
                        className="font-mono text-sm max-w-md bg-black/50" 
                      />
                      <Button variant="secondary" onClick={handleSave}>Save</Button>
                    </div>
                    <p className="text-xs text-muted-foreground">Required for reading remote repositories.</p>
                  </div>
                </CardContent>
              </Card>
            </section>

          </div>
        </div>
      </MainContent>
    </SidebarLayout>
  );
}
