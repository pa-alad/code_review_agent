# Code Review Agent

Code Review Agent is a Dockerised FastAPI application that reviews GitHub snapshots
with deterministic best-practice checks and presents a proposed unified diff.
An optional AI pass can add repository-aware, advisory findings through a local
Ollama service or Google's Gemini API.

The code in the specified repository will be reviewed according to a selected software development best practice "lens".

## Run locally with Docker

```sh
docker build -t lens-review .
docker run --rm -p 8000:8000 lens-review
```

Open http://localhost:8000.

Set `GITHUB_TOKEN` when reviewing private repositories or when higher GitHub API limits are needed:

```sh
docker run --rm -p 8000:8000 -e GITHUB_TOKEN="$GITHUB_TOKEN" lens-review
```

## Inputs

- Repository URL: scans supported files at the repository default branch.
- File URL: accepts GitHub's `/blob/{branch-or-commit}/{path}` form and uses that revision.
- Branch or commit: optional override for repository URLs and explicit control of the requested snapshot.

The current version supports Python, C, C++, Java, and Bash files and offers Clean
Code, SOLID, C++ Core Guidelines, and SEI CERT Secure Coding lenses. Each lens
declares the languages it supports; irrelevant files are skipped and shown in the
result. Proposed changes include language-appropriate comments with the rule's
source reference.

## Optional AI review

AI review is disabled unless a provider is configured and the user explicitly
checks the AI option for a review. Existing deterministic checks work without an
AI provider. AI findings are advisory, source-grounded suggestions: the model
does not apply edits, execute code, or create commits. Provider failures do not
discard deterministic findings.

The request context is limited to 24 files, at most 8,000 characters per file,
and 64,000 characters total. Up to six recognized project-guidance files
(`README.md`, `CONTRIBUTING.md`, root or nested `AGENTS.md`, and
`.github/copilot-instructions.md`) are fetched only when AI review is requested;
the same context limits apply, with a 24,000-character fetch cap for guidance.
The review response reports when context was truncated or omitted. These limits
bound prompt size, not the size of the initial GitHub snapshot fetch.

### Local inference with Ollama

Install [Ollama](https://ollama.com/) and download a small coding model, for
example `qwen2.5-coder:3b`:

```sh
ollama pull qwen2.5-coder:3b
LLM_PROVIDER=ollama LLM_MODEL=qwen2.5-coder:3b uvicorn app.main:app --reload
```

Ollama model memory usage depends on the model, quantization, and context size;
the 3B model is a lightweight starting point, not a fixed hardware guarantee.
The model runs outside this application. If the application itself runs in
Docker while Ollama runs on the host, configure a host-reachable Ollama URL. On
Linux this can require binding Ollama to a network interface and adding a host
gateway to the container, for example:

```sh
docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway \
	-e LLM_PROVIDER=ollama \
	-e OLLAMA_BASE_URL=http://host.docker.internal:11434 lens-review
```

Ensure the Ollama service is not exposed to untrusted networks.

### Remote inference with Gemini

Create a Gemini API key, then run the application with:

```sh
LLM_PROVIDER=gemini GEMINI_API_KEY="$GEMINI_API_KEY" uvicorn app.main:app --reload
```

The default model is `gemini-2.5-flash`; `LLM_MODEL` can select another model
available to your API key. Free-tier model access, quotas, availability, and
terms can change. Check Google's current [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
and [terms](https://ai.google.dev/gemini-api/terms) before use. Free-tier
submissions may be used to improve Google's products. The UI requires separate
confirmation before any repository context is sent to Gemini. Do not use this
option for confidential code unless the applicable terms are acceptable. To keep
remote use free, use a Google AI Studio project with free-tier access and do not
enable billing; the application cannot prevent charges if configured with a
billable project or provider account.

Only the provider choice and model name are exposed to the browser; API keys stay
server-side. Configure `LLM_PROVIDER=none` (the default) to disable AI review.

GitHub MCP is not required. The container calls GitHub's API directly so it can
run independently of VS Code. Pull-request creation is intentionally deferred.

## Local tests

```sh
python3 -m pip install -e '.[test]'
python3 -m pytest
```
