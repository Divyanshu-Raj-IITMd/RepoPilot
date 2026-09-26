# LLM Providers — all free

RepoPilot works with **no LLM at all** (offline heuristic mode: agents' structured
findings and citations are deterministic; narration uses templates). Adding a
provider only improves the prose — never the evidence.

Selection order (`REPOPILOT_LLM_PROVIDER=auto`, the default):

```
GROQ_API_KEY  →  GEMINI_API_KEY/GOOGLE_API_KEY  →  OPENROUTER_API_KEY
→  Ollama reachable at OLLAMA_URL  →  heuristic (offline)
```

Set `REPOPILOT_LLM_PROVIDER` explicitly to pin one: `groq | gemini | openrouter | ollama | heuristic`.

The current provider is visible in the UI sidebar and at `GET /api/health`.

## Ollama — 100% local, free, private

```bash
# install: https://ollama.com/download
ollama pull qwen2.5-coder:7b        # 4.7 GB, great at code; or llama3.1:8b, etc.
export REPOPILOT_LLM_PROVIDER=ollama
export REPOPILOT_OLLAMA_MODEL=qwen2.5-coder:7b
# optional: OLLAMA_URL=http://127.0.0.1:11434
```

No data ever leaves the machine. If the configured model isn't installed,
RepoPilot automatically falls back to the first installed model.

## Groq — free tier, very fast

```bash
export GROQ_API_KEY="gsk_..."       # console.groq.com → API Keys
# default model: llama-3.3-70b-versatile (free tier)
```

OpenAI-compatible REST; generous free quota, ideal for demos.

## Google Gemini — free tier

```bash
export GEMINI_API_KEY="AIza..."     # aistudio.google.com → Get API key
# default model: gemini-2.0-flash
```

## OpenRouter — free community models

```bash
export OPENROUTER_API_KEY="sk-or-..."
# default model: meta-llama/llama-3.3-70b-instruct:free
```

## Embeddings (optional upgrade)

```bash
pip install sentence-transformers        # auto-used by REPOPILOT_EMBEDDER=auto
export REPOPILOT_SBERT_MODEL="sentence-transformers/all-MiniLM-L6-v2"  # default
```

Without it, RepoPilot uses the built-in deterministic hashing TF-IDF embedder —
weaker semantics, zero downloads, CI-friendly. Retrieval is hybrid, so symbol
and graph signals still carry exact-name queries.

## Privacy note

Content sent to **remote** providers (Groq/Gemini/OpenRouter) passes through
`redact()` first — secret-looking spans (API keys, DSNs with passwords, tokens)
are masked as `***REDACTED***` before leaving the process. Ollama and heuristic
modes never send anything anywhere.
