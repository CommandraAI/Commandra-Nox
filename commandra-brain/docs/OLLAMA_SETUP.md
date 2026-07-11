# Connecting Commandra Nox Brain to Ollama

Commandra Nox Brain is **local-first by design**: all planning, reasoning,
repository indexing, semantic search, context selection, memory, and
multi-agent orchestration happen inside the Brain itself, in plain Python,
with zero cloud dependencies. The only thing an external model provider is
asked to do is **generate text from a prompt the Brain has already built**.
[Ollama](https://ollama.com) is the supported way to do that on your own
machine — no API keys, no cloud calls, no data ever leaves your computer.

This guide covers installing Ollama, pulling a coding model, running it, and
pointing Commandra at it.

## 1. Install Ollama

- **macOS**: download from https://ollama.com/download or `brew install ollama`
- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`
- **Windows**: download the installer from https://ollama.com/download

Verify the install:

```bash
ollama --version
```

## 2. Pull a coding model

Commandra defaults to `qwen2.5-coder:7b`, a strong general-purpose coding
model that runs comfortably on consumer hardware (needs roughly 8GB of RAM
free). Pull it with:

```bash
ollama pull qwen2.5-coder:7b
```

### Other supported models

Any model available in the Ollama library works — set `OLLAMA_MODEL` (see
below) to whichever tag you pull. Good coding-focused options:

| Model | Tag | Notes |
|---|---|---|
| Qwen2.5-Coder | `qwen2.5-coder:7b` (default), `qwen2.5-coder:14b`, `qwen2.5-coder:32b` | Best all-round balance of quality/speed for most machines |
| DeepSeek-Coder V2 | `deepseek-coder-v2:16b` | Strong reasoning, larger footprint |
| Code Llama | `codellama:13b`, `codellama:34b` | Meta's coding model, well-tested |
| StarCoder2 | `starcoder2:15b` | Good for completion-heavy workloads |
| Llama 3.1 | `llama3.1:8b` | General-purpose fallback if you want one model for everything |

Bigger models produce better plans and code but need more RAM/VRAM and are
slower per token. Start with the 7B-class default and size up only if you
have the hardware and want higher quality.

## 3. Run Ollama locally

On macOS and Windows the installer sets up Ollama as a background service
automatically. On Linux, start it manually if it isn't already running as a
systemd service:

```bash
ollama serve
```

By default Ollama listens on `http://localhost:11434`. You can confirm it's
up with:

```bash
curl http://localhost:11434/api/tags
```

This should return JSON listing the models you've pulled.

## 4. Point Commandra at Ollama

Commandra's Brain server picks its AI provider from the `AI_PROVIDER`
environment variable:

```bash
# Use the real local model (requires Ollama running, see above)
export AI_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434   # optional, this is the default
export OLLAMA_MODEL=qwen2.5-coder:7b            # optional, this is the default

python -m server.main
```

Leave `AI_PROVIDER` unset (or set it to `mock`) to run entirely offline
against the built-in deterministic `MockProvider` — useful for development,
testing the Brain's pipeline, or CI, without needing Ollama installed at all.

You can also switch providers at runtime without restarting the server:

```bash
curl -X POST http://localhost:8000/provider \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama", "baseUrl": "http://localhost:11434", "model": "qwen2.5-coder:7b"}'
```

## 5. How the Brain talks to Ollama

The Brain never sends your raw message straight to the model. Every request
passes through this pipeline first (see `brain/orchestrator.py`):

1. **Planning Engine** classifies intent and complexity, and builds an
   ordered step plan.
2. **Context Engine** decides which files, if any, are relevant (TF-IDF
   ranking over indexed chunks + one-hop import graph traversal) — it never
   dumps the whole repository into the prompt.
3. **Reasoning Engine** produces a short chain of reasoning grounded in the
   plan, selected context, and long-term memory.
4. **Memory Engine** recalls prior architecture notes/decisions recorded for
   this repository.
5. A specialist **Agent** (coding, review, testing, security, etc.) builds
   the final prompt from all of the above and calls the active `AIProvider`.
6. The **Response Optimizer** cleans up the raw model output before it's
   returned.

Only step 5 ever touches Ollama. `providers/ollama_provider.py` implements
this as a plain HTTP client against Ollama's native API:

- `GET /api/tags` — list installed models (used for health/availability
  checks)
- `POST /api/generate` — the actual generation call, with streaming
  (NDJSON) support

### Example: calling Ollama's API directly

If you want to test Ollama independently of Commandra:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5-coder:7b",
  "prompt": "Write a Python function that reverses a linked list.",
  "stream": false
}'
```

### Example: calling Commandra's Brain (which then calls Ollama)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain the architecture of this repository"}'
```

The response includes the plan, reasoning trace, selected context files, and
the final markdown answer — regardless of which provider generated it.

## 6. Troubleshooting

**"Connection refused" / provider shows `available: false`**
Ollama isn't running, or is running on a different host/port than
`OLLAMA_BASE_URL` points to. Run `ollama serve` and re-check
`curl $OLLAMA_BASE_URL/api/tags`.

**"model not found"**
The model tag in `OLLAMA_MODEL` hasn't been pulled yet. Run
`ollama pull <model>` with the exact tag (`ollama list` shows what's already
installed).

**Responses are slow**
Larger models are compute-heavy. Try a smaller tag (e.g. `qwen2.5-coder:7b`
instead of `:32b`), make sure you're not also running other GPU/CPU-heavy
processes, and check `ollama ps` to see what's currently loaded in memory.

**Out of memory / model won't load**
Pick a smaller model, or quantized variant (most Ollama tags are already
quantized by default — check the model's tag list on ollama.com/library for
lighter options).

**Commandra still shows Mock responses after switching providers**
Confirm `AI_PROVIDER=ollama` was set before starting `server.main`, or that
you called `POST /provider` with `"provider": "ollama"` — restart the Brain
server workflow if you only changed the environment variable.

## 7. Local-first, by construction

Nothing in this project calls any cloud AI API. `providers/mock_provider.py`
and `providers/ollama_provider.py` are the only two ways text ever gets
generated, and both are fully local: `MockProvider` runs in-process with no
network calls at all, and `OllamaProvider` only ever talks to the
`OLLAMA_BASE_URL` you configure — which should always be a machine you
control (`localhost` in the common case). There is no telemetry, no
third-party API keys, and no code path that reaches outside your own
network.
