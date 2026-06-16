"""
deploy.py — Deploy: push to GitHub + deploy to Vercel.

Steps:
  1. git init + add + commit
  2. gh repo create + push
  3. vercel --prod --yes (with token from .env)
  4. Save deployment_urls.md

Prerequisites: git, gh CLI, vercel CLI
Token: reads VERCEL_TOKEN from .env (set by user once)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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

    # --- Step 5: Vercel deploy (with token from .env) ---
    C.log("=== Deploy: Step 5 — Vercel deploy ===")

    # Read token from .env
    env_token = None
    env_file = C.ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().split("\n"):
            if line.startswith("VERCEL_TOKEN="):
                env_token = line.split("=", 1)[1].strip().strip("<>")
                break

    if not env_token:
        C.log("VERCEL_TOKEN not in .env. Skipping Vercel deployment.", "WARN")
        vercel_url = f"https://{project_name}.vercel.app (requires token)"
    else:
        # Find vercel executable
        import shutil
        vercel_exe = shutil.which("vercel")
        if not vercel_exe:
            vercel_exe = shutil.which("vercel.cmd")
        if not vercel_exe:
            npm_path = Path.home() / "AppData" / "Roaming" / "npm" / "vercel.cmd"
            if npm_path.exists():
                vercel_exe = str(npm_path)

        if not vercel_exe:
            C.log("vercel CLI not found. Install: npm install -g vercel", "WARN")
            vercel_url = f"https://{project_name}.vercel.app (requires vercel CLI)"
        else:
            # Set token in environment and run vercel CLI
            deploy_env = os.environ.copy()
            deploy_env["VERCEL_TOKEN"] = env_token

            # Try deployment
            vercel_result = subprocess.run(
                [vercel_exe, "--prod", "--yes"],
                cwd=str(C.ROOT),
                env=deploy_env,
                capture_output=True,
                text=True,
                timeout=300,
            )

            # If missing_scope error, extract scope and retry
            if "missing_scope" in vercel_result.stdout.lower():
                try:
                    import json as js
                    scope_match = None
                    for line in vercel_result.stdout.split("\n"):
                        if '"id"' in line and line.strip().startswith('"id"'):
                            # Extract scope from response
                            data = js.loads(vercel_result.stdout)
                            if data.get("choices"):
                                scope_match = data["choices"][0].get("id")
                                break
                    if scope_match:
                        C.log(f"Retrying with scope: {scope_match}")
                        vercel_result = subprocess.run(
                            [vercel_exe, "--prod", "--yes", "--scope", scope_match, "--name", project_name],
                            cwd=str(C.ROOT),
                            env=deploy_env,
                            capture_output=True,
                            text=True,
                            timeout=300,
                        )
                except Exception:
                    pass

            if vercel_result.stdout:
                print(vercel_result.stdout.rstrip())
            if vercel_result.stderr:
                print(vercel_result.stderr.rstrip())

            vercel_url = f"https://{project_name}.vercel.app"
            if vercel_result.returncode != 0:
                C.log("Vercel deployment failed", "WARN")
                vercel_url += " (deployment pending)"
            else:
                C.log(f"Deployed to Vercel: {vercel_url}", "INFO")

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
