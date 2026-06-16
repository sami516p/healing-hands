# Directive: Deployment — Preview + GitHub + Vercel

## Purpose
After Gemini's visual review is accepted, give the user a live localhost preview to make final edits, then automatically deploy to GitHub (public repo) and Vercel (production static hosting).

## Phase Sequence

| # | Label | Owner | Action | Output |
|---|-------|-------|--------|--------|
| 10 | Preview | **You** | Site served at localhost:8000; edit freely | Edited site files |
| — | Advance Preview | Supervisor | `supervisor.py advance preview` | Stops server; validates HTML; transitions to PREVIEW_DONE |
| 11 | Deploy | Supervisor (`deploy.py`) | GitHub push + Vercel prod deploy | `.tmp/deployment_urls.md`, live URLs |
| 12 | Archive | Supervisor | `supervisor.py run` (auto after DEPLOYED) | `archives/{name}/{timestamp}/` |

## Prerequisites

All three must be installed globally and authenticated before the pipeline reaches PREVIEW:

| Tool | Check | Install |
|------|-------|---------|
| `git` | `git --version` | https://git-scm.com |
| `gh` (GitHub CLI) | `gh auth status` | `winget install GitHub.cli` |
| `vercel` (Vercel CLI) | `vercel --version` | `npm i -g vercel`, then `vercel login` |

## Preview Phase (Phase 10)

The supervisor starts `execution/serve.py` as a detached background process and opens the browser automatically. The server:
- Serves the project root at `http://localhost:8000/`
- Resolves `css/`, `js/`, `assets/` correctly (runs `os.chdir(ROOT)`)
- Runs until `advance preview` kills it via PID file (`.tmp/preview_server.pid`)

**What you can do during preview:**
- Edit `index.html`, `css/style.css`, `js/`, or swap images in `assets/images/`
- Hard-refresh the browser (`Ctrl+Shift+R`) to see changes live
- Run `supervisor.py validate preview` at any point to confirm HTML is still valid
- Run `supervisor.py status` to check pipeline state

**When done editing:**
```
python execution/supervisor.py advance preview
```

This: (1) validates HTML structure, (2) kills the server, (3) sets PREVIEW_DONE, (4) auto-starts deploy.

## Deploy Phase (Phase 11) — `execution/deploy.py`

Steps executed in order:

1. **`.gitignore` guard** — Appends `.vercel/` if not already present (prevents Vercel config from polluting commits)
2. **`git init -b main`** — Skipped if `.git/` already exists; uses `main` for GitHub compatibility
3. **`git add . && git commit -m "Deploy {project_name}"`** — Commits all non-ignored files. "Nothing to commit" (rc=1) is treated as success for re-deploy scenarios
4. **`gh repo create {project_name} --public --source=. --remote=origin --push`** — Creates public GitHub repo and pushes in one step. If repo already exists: detects "already exists" in stderr, adds remote if missing, force-pushes to `main`
5. **`vercel --prod --yes`** — Static deploy streamed live to terminal; `--yes` accepts all defaults on first run, `.vercel/project.json` is used on re-deploy
6. **Writes `.tmp/deployment_urls.md`** — Records GitHub URL + Vercel URL + timestamp for archive record
7. **Sets state to `DEPLOYED`** — Supervisor's next `run` call triggers archive automatically

## Error Handling

| Problem | Detection | Recovery |
|---------|-----------|----------|
| GitHub repo name already taken | `gh` stderr contains "already exists" | Push to existing remote; handled automatically |
| `vercel --yes` still prompts | Non-zero exit code | Run `vercel login` then retry; or `vercel link --yes` to pre-link the project |
| HTML invalid after preview edits | `validate preview` fails in `advance preview` | Fix the HTML, then re-run `advance preview` |
| `git commit` nothing to commit | rc=1 | Treated as success; skips commit, continues |
| Port 8000 already in use | `serve.py` raises `OSError` on bind | Kill the occupying process: `netstat -aon | findstr :8000` then `taskkill /PID <id>` |
| Preview server already running (re-run during PREVIEW) | Supervisor detects PREVIEW state | Prints banner reminder; does NOT start second server |

## Post-Deploy URLs

Both URLs are written to `.tmp/deployment_urls.md` and stored in `.tmp/supervisor_state.json`:
- **GitHub:** `https://github.com/{gh_user}/{project_name}`
- **Vercel:** `https://{project_name}.vercel.app` (approximated; canonical URL is in Vercel CLI output)

## What Gets Cleaned Up After Archive

`_reset_workspace()` deletes `.git/` and `.vercel/` in addition to standard cleanup. Each new project starts with a fresh git history and an unlinked Vercel project. This prevents project A's Vercel config from being used for project B.

## Hard Rules
- Never deploy without a passing `validate preview` — enforced by `advance preview`.
- Never skip the preview step — `PREVIEW_DONE` state is required before `deploy.py` runs.
- The GitHub repo is always **public** by default. To make it private, change `--public` to `--private` in `deploy.py` step 4.
- `deploy.py` does not modify `index.html`, `css/`, or `js/` — it only commits what exists.
- Do not manually set state to `PREVIEW_DONE` to skip the preview — the server must actually stop cleanly.
