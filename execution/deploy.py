"""
deploy.py — Phase 11 (Deploy): push to GitHub + deploy to Vercel.

Called by supervisor.py after the user finishes preview edits and runs
`supervisor.py advance preview`. Steps:

  1. Ensure .gitignore has .vercel/ entry
  2. git init -b main (if .git/ absent)
  3. git add . && git commit
  4. gh repo create {name} --public --source=. --remote=origin --push
     (if repo exists: push to existing remote)
  5. vercel --prod --yes  (streams live)
  6. Write .tmp/deployment_urls.md
  7. Write DEPLOYED state

Prerequisites: git, gh CLI, and vercel CLI — all globally installed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Ensure execution/ is on path when run standalone
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd, cwd=str(C.ROOT), capture_output=True, text=True, timeout=300
    )
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip())
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed (rc={result.returncode}): {' '.join(cmd)}"
        )
    return result


def _ensure_gitignore_has(entry: str) -> None:
    gi = C.ROOT / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if entry not in text:
        with gi.open("a", encoding="utf-8") as fh:
            fh.write(f"\n# Vercel project config (machine-specific)\n{entry}\n")
        C.log(f"Added '{entry}' to .gitignore")


def _get_gh_user() -> str:
    r = subprocess.run(
        ["gh", "api", "user", "-q", ".login"],
        capture_output=True, text=True, timeout=30, cwd=str(C.ROOT)
    )
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def main() -> None:
    state = C.read_state()
    project_name = state.get("project_name") or "project"

    # --- Step 1: .gitignore guard ---
    C.log("=== Deploy: Step 1 — Ensure .gitignore ===")
    _ensure_gitignore_has(".vercel/")

    # --- Step 2: git init ---
    C.log("=== Deploy: Step 2 — Git init ===")
    if not (C.ROOT / ".git").exists():
        _run(["git", "init", "-b", "main"])
        C.log("git init done (branch: main)")
    else:
        C.log("Git repo already exists, skipping init")

    # --- Step 3: stage + commit ---
    C.log("=== Deploy: Step 3 — Git add + commit ===")
    _run(["git", "add", "."])
    commit_result = _run(
        ["git", "commit", "-m", f"Deploy {project_name}"],
        check=False,
    )
    # rc=1 with "nothing to commit" is OK; any other non-zero is a real failure
    if commit_result.returncode not in (0, 1):
        raise RuntimeError(f"git commit failed (rc={commit_result.returncode})")
    C.log("git commit done")

    # --- Step 4: GitHub repo ---
    C.log("=== Deploy: Step 4 — GitHub repo ===")
    gh_user = _get_gh_user()
    repo_url = f"https://github.com/{gh_user}/{project_name}"

    create_result = _run(
        ["gh", "repo", "create", project_name,
         "--public", "--source=.", "--remote=origin", "--push"],
        check=False,
    )
    if create_result.returncode != 0:
        stderr = (create_result.stderr or "").lower()
        if "already exists" in stderr or "name already exists" in stderr:
            C.log(f"Repo '{project_name}' already exists — pushing to existing remote")
            remote_check = _run(["git", "remote", "get-url", "origin"], check=False)
            if remote_check.returncode != 0:
                _run(["git", "remote", "add", "origin",
                      f"https://github.com/{gh_user}/{project_name}.git"])
            _run(["git", "push", "-u", "origin", "main", "--force"])
            C.log("Pushed to existing GitHub repo")
        else:
            raise RuntimeError(
                f"gh repo create failed (rc={create_result.returncode}): "
                f"{create_result.stderr}"
            )
    else:
        C.log(f"GitHub repo created and pushed: {repo_url}")

    # --- Step 5: Vercel deploy (streamed live) ---
    C.log("=== Deploy: Step 5 — Vercel deploy ===")
    vercel_result = subprocess.run(
        ["vercel", "--prod", "--yes"],
        cwd=str(C.ROOT), text=True, timeout=300,
        # capture_output=False so the user sees Vercel's live progress
    )
    if vercel_result.returncode != 0:
        raise RuntimeError(f"vercel deploy failed (rc={vercel_result.returncode})")

    # Approximate Vercel URL from project name (canonical URL is in CLI output above)
    vercel_url = f"https://{project_name}.vercel.app"

    # --- Step 6: Write deployment URLs ---
    C.log("=== Deploy: Step 6 — Record deployment URLs ===")
    url_doc = (
        f"# Deployment URLs — {project_name}\n\n"
        f"- **GitHub:** {repo_url}\n"
        f"- **Vercel:** {vercel_url}\n"
        f"- **Deployed at:** {C.now()}\n"
    )
    (C.TMP / "deployment_urls.md").write_text(url_doc, encoding="utf-8")

    C.log(f"GitHub : {repo_url}")
    C.log(f"Vercel : {vercel_url}")
    C.log("Deployment complete.")

    # --- Step 7: Advance state ---
    C.write_state("DEPLOYED", github_url=repo_url, vercel_url=vercel_url)


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except RuntimeError as e:
        C.log(str(e), "ERROR")
        try:
            (C.TMP / "deploy_error.txt").write_text(str(e), encoding="utf-8")
        except OSError:
            pass
        sys.exit(1)
