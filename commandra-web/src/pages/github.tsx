import { AppSidebar } from "@/components/layout/app-sidebar";
import { MainContent, SidebarLayout } from "@/components/layout/sidebar-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  useListRepos,
  useAddRepo,
  getListReposQueryKey
} from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { FolderGit2, Plus, GitBranch, Terminal, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/hooks/use-toast";

export function GithubPage() {
  const [repoPath, setRepoPath] = useState("");
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: repos } = useListRepos({
    query: { queryKey: getListReposQueryKey() }
  });

  const addRepo = useAddRepo({
    mutation: {
      onSuccess: () => {
        setRepoPath("");
        queryClient.invalidateQueries({ queryKey: getListReposQueryKey() });
        toast({ title: "Repository tracked" });
      },
      onError: (err) => {
        toast({ title: "Failed to add repo", variant: "destructive" });
      }
    }
  });

  const handleAddRepo = (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoPath) return;
    addRepo.mutate({ data: { path: repoPath } });
  };

  return (
    <SidebarLayout>
      <AppSidebar />
      <MainContent className="bg-background">
        <div className="h-14 border-b border-white/5 flex items-center px-6">
          <h1 className="font-semibold text-lg flex items-center gap-2">
            <FolderGit2 className="w-5 h-5 text-muted-foreground" />
            Workspace Repositories
          </h1>
        </div>

        <div className="flex-1 overflow-auto p-6 lg:p-10">
          <div className="max-w-4xl mx-auto space-y-8">
            
            {/* Add Repo Card */}
            <Card className="bg-[#111] border-white/10 border-dashed">
              <CardHeader className="pb-4">
                <CardTitle className="text-base">Track Local Repository</CardTitle>
                <CardDescription>Enter the absolute path to a local git repository to allow Commandra to read its context.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleAddRepo} className="flex gap-3">
                  <div className="relative flex-1 max-w-xl">
                    <Terminal className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input 
                      value={repoPath}
                      onChange={(e) => setRepoPath(e.target.value)}
                      placeholder="/home/user/projects/my-app"
                      className="pl-9 font-mono bg-black/50 border-white/10"
                    />
                  </div>
                  <Button type="submit" disabled={addRepo.isPending} className="w-[120px]">
                    {addRepo.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <><Plus className="w-4 h-4 mr-2" /> Track Repo</>}
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Repos List */}
            <div className="space-y-4">
              <h2 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground font-mono">Tracked Workspaces</h2>
              
              <div className="grid gap-3">
                {repos?.length === 0 ? (
                  <div className="text-center py-12 border border-dashed rounded-lg border-white/10 bg-black/20 text-muted-foreground">
                    No repositories tracked yet.
                  </div>
                ) : null}

                {repos?.map((repo) => (
                  <div key={repo.id} className="flex items-center justify-between p-4 rounded-lg border border-white/5 bg-[#161616] hover:bg-[#1a1a1a] transition-colors group">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded bg-white/5 border border-white/5 flex items-center justify-center">
                        <FolderGit2 className="w-5 h-5 text-primary" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-[15px]">{repo.name}</h3>
                        <p className="text-xs font-mono text-muted-foreground">{repo.path}</p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-6">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-black/40 px-2 py-1 rounded border border-white/5">
                        <GitBranch className="w-3.5 h-3.5" />
                        {repo.branch}
                      </div>
                      <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity">
                        View Tree
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </MainContent>
    </SidebarLayout>
  );
}
