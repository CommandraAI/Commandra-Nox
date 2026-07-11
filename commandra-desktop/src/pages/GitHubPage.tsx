import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, GitBranch, Folder, FileText, ChevronRight, ChevronDown, Loader2 } from 'lucide-react';
import { api, type Repo, type FileNode } from '../lib/api';
import { cn, timeAgo } from '../lib/utils';

export default function GitHubPage() {
  const qc = useQueryClient();
  const [addPath, setAddPath] = useState('');
  const [adding, setAdding] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);
  const [selectedFile, setSelectedFile] = useState<{ path: string; content: string; language?: string } | null>(null);

  const { data: repos = [] } = useQuery({
    queryKey: ['repos'],
    queryFn: api.repos.list,
  });

  const addMutation = useMutation({
    mutationFn: (path: string) => api.repos.add({ path }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['repos'] });
      setAddPath('');
      setAdding(false);
    },
  });

  const removeMutation = useMutation({
    mutationFn: api.repos.remove,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['repos'] });
      if (selectedRepo) setSelectedRepo(null);
    },
  });

  const { data: tree = [] } = useQuery({
    queryKey: ['tree', selectedRepo?.id],
    queryFn: () => api.repos.tree(selectedRepo!.id),
    enabled: !!selectedRepo,
  });

  const openFile = async (repoId: number, path: string) => {
    try {
      const file = await api.repos.readFile(repoId, path);
      setSelectedFile(file);
    } catch {}
  };

  return (
    <div className="flex-1 flex h-full overflow-hidden">
      {/* Repo list */}
      <div className="w-64 border-r border-[#1e1e1e] flex flex-col overflow-hidden">
        <div className="px-4 py-4 border-b border-[#1e1e1e] flex items-center justify-between">
          <h2 className="text-xs font-semibold text-[#555] uppercase tracking-wider">Repositories</h2>
          <button
            onClick={() => setAdding((v) => !v)}
            className="w-5 h-5 flex items-center justify-center rounded text-[#555] hover:text-[#888] hover:bg-[#1a1a1a]"
          >
            <Plus size={12} />
          </button>
        </div>

        {adding && (
          <div className="px-3 py-2 border-b border-[#1e1e1e]">
            <input
              value={addPath}
              onChange={(e) => setAddPath(e.target.value)}
              placeholder="/path/to/repo"
              className="w-full bg-[#111] border border-[#2a2a2a] rounded px-2.5 py-1.5 text-xs text-[#ccc] outline-none font-mono focus:border-[#333]"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && addPath.trim()) addMutation.mutate(addPath.trim());
                if (e.key === 'Escape') setAdding(false);
              }}
              autoFocus
            />
            <p className="text-[10px] text-[#444] mt-1">Press Enter to add</p>
          </div>
        )}

        <div className="flex-1 overflow-y-auto py-1">
          {repos.map((repo) => (
            <button
              key={repo.id}
              onClick={() => { setSelectedRepo(repo); setSelectedFile(null); }}
              className={cn(
                'w-full flex items-start gap-2.5 px-3 py-2.5 text-left transition-colors group',
                selectedRepo?.id === repo.id
                  ? 'bg-[#1a1a1a] text-[#e8e8e8]'
                  : 'text-[#777] hover:bg-[#141414] hover:text-[#bbb]'
              )}
            >
              <Folder size={13} className="shrink-0 mt-0.5 opacity-60" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{repo.name}</p>
                <div className="flex items-center gap-1 mt-0.5">
                  <GitBranch size={9} className="text-[#444]" />
                  <span className="text-[10px] text-[#444] font-mono">{repo.branch}</span>
                </div>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); removeMutation.mutate(repo.id); }}
                className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center rounded text-[#444] hover:text-red-500"
              >
                <Trash2 size={10} />
              </button>
            </button>
          ))}
          {repos.length === 0 && (
            <div className="px-4 py-6 text-center">
              <p className="text-xs text-[#444]">No repositories added</p>
              <p className="text-[10px] text-[#333] mt-1">Click + to add a local repo</p>
            </div>
          )}
        </div>
      </div>

      {/* File tree */}
      {selectedRepo && (
        <div className="w-56 border-r border-[#1e1e1e] flex flex-col overflow-hidden">
          <div className="px-3 py-3 border-b border-[#1e1e1e]">
            <p className="text-xs font-medium text-[#888] truncate">{selectedRepo.name}</p>
            <p className="text-[10px] text-[#444] font-mono mt-0.5">{selectedRepo.path}</p>
          </div>
          <div className="flex-1 overflow-y-auto py-1 px-1">
            {tree.map((node) => (
              <FileTreeNode
                key={node.path}
                node={node}
                depth={0}
                onFile={(path) => openFile(selectedRepo.id, path)}
              />
            ))}
          </div>
        </div>
      )}

      {/* File viewer */}
      {selectedFile ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#1e1e1e] flex items-center gap-2">
            <FileText size={12} className="text-[#555]" />
            <span className="text-xs text-[#666] font-mono">{selectedFile.path}</span>
            {selectedFile.language && (
              <span className="ml-auto text-[10px] text-[#444] border border-[#1e1e1e] px-1.5 py-0.5 rounded">
                {selectedFile.language}
              </span>
            )}
          </div>
          <div className="flex-1 overflow-auto p-4">
            <pre className="text-[12px] text-[#999] font-mono leading-relaxed whitespace-pre selectable">
              {selectedFile.content}
            </pre>
          </div>
        </div>
      ) : selectedRepo ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-[#333]">Select a file to view</p>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-[#333]">Select a repository</p>
        </div>
      )}
    </div>
  );
}

function FileTreeNode({
  node, depth, onFile,
}: { node: FileNode; depth: number; onFile: (path: string) => void }) {
  const [open, setOpen] = useState(depth === 0);

  if (node.type === 'directory') {
    return (
      <div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 w-full px-2 py-1 rounded text-[#555] hover:text-[#888] hover:bg-[#141414] text-xs"
          style={{ paddingLeft: `${8 + depth * 12}px` }}
        >
          {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          <Folder size={11} className="opacity-60" />
          <span className="truncate">{node.name}</span>
        </button>
        {open && node.children?.map((child) => (
          <FileTreeNode key={child.path} node={child} depth={depth + 1} onFile={onFile} />
        ))}
      </div>
    );
  }

  return (
    <button
      onClick={() => onFile(node.path)}
      className="flex items-center gap-1.5 w-full px-2 py-1 rounded text-[#555] hover:text-[#888] hover:bg-[#141414] text-xs"
      style={{ paddingLeft: `${8 + depth * 12}px` }}
    >
      <FileText size={11} className="opacity-40 shrink-0" />
      <span className="truncate">{node.name}</span>
    </button>
  );
}
