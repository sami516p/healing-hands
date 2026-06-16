"""
_common.py — shared helpers for the execution layer.

Every execution script imports from here so paths, state, logging, and the
project-input parser stay consistent across the whole pipeline. This is an
internal helper module (not a "tool" / directive target) — it exists only so
the four real scripts (discover_business, collect_assets, fetch_reference_site,
supervisor) don't duplicate plumbing.

Design rules:
- No third-party imports here. Pure stdlib so importing this never fails.
- All paths are derived from this file's location, so scripts work no matter
  what the current working directory is.
"""

from __future__ import annotations

import json
import re
import sys
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — execution/_common.py  →  ROOT is the parent of execution/
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
EXECUTION = ROOT / "execution"
DIRECTIVES = ROOT / "directives"
INPUTS = ROOT / "inputs"
TMP = ROOT / ".tmp"
ASSETS = ROOT / "assets"
IMAGES = ASSETS / "images"
ARCHIVES = ROOT / "archives"

PROJECT_INPUT = INPUTS / "project_input.md"
STATE_FILE = TMP / "supervisor_state.json"
STATUS_FILE = TMP / "supervisor_status.md"
HEALING_LOG = TMP / "healing_log.md"

# Build outputs that live at the project root (rotated per project).
BUILD_OUTPUTS = ["index.html", "css", "js"]

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
STATES = [
    "CLEAN",
    "DISCOVERY_DONE",
    "ASSETS_DONE",
    "REFERENCE_DONE",
    "SECTIONS_DONE",
    "AWAITING_GEMINI_BRIEF",
    "BRIEF_READY",
    "CODE_DONE",
    "DEBUG_DONE",
    "AWAITING_GEMINI_REVIEW",
    "REVIEW_DONE",
    "PREVIEW",
    "REVISING",
    "PREVIEW_DONE",
    "DEPLOYED",
    "ARCHIVED",
]


def now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_slug() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def log(msg: str, level: str = "INFO") -> None:
    """Timestamped line to stdout. The supervisor's single reporting channel."""
    print(f"[{now()}] {level:5} | {msg}", flush=True)


def ensure_dirs() -> None:
    """Create the working directories. Safe to call repeatedly."""
    for d in (TMP, ASSETS, IMAGES, INPUTS, ARCHIVES, DIRECTIVES):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# State read / write
# ---------------------------------------------------------------------------
def read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log("supervisor_state.json unreadable — treating as CLEAN", "WARN")
    return {"state": "CLEAN", "project_name": None, "updated": now(), "history": []}


def write_state(state: str, project_name: str | None = None, **extra) -> dict:
    cur = read_state()
    if state not in STATES and state != "CLEAN":
        log(f"Unknown state '{state}' — writing anyway", "WARN")
    cur["state"] = state
    if project_name is not None:
        cur["project_name"] = project_name
    cur["updated"] = now()
    cur.setdefault("history", []).append({"state": state, "at": now()})
    cur.update(extra)
    ensure_dirs()
    STATE_FILE.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    return cur


# ---------------------------------------------------------------------------
# Healing log — the self-annealing audit trail
# ---------------------------------------------------------------------------
def log_healing(problem: str, solution: str, file_updated: str = "—") -> None:
    ensure_dirs()
    header = ""
    if not HEALING_LOG.exists():
        header = "# Healing Log\n\nEvery novel problem the supervisor solved, and the file it upgraded so it won't recur.\n\n"
    entry = (
        f"## {now()}\n"
        f"- **Problem:** {problem}\n"
        f"- **Solution:** {solution}\n"
        f"- **File upgraded:** {file_updated}\n\n"
    )
    with HEALING_LOG.open("a", encoding="utf-8") as fh:
        fh.write(header + entry)
    log(f"Self-heal logged: {problem} -> {solution} (updated {file_updated})", "HEAL")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def slugify(text: str, maxlen: int = 40) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return (text or "untitled")[:maxlen]


def write_json(path: Path, data) -> None:
    ensure_dirs()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default
    return default


# ---------------------------------------------------------------------------
# project_input.md parser
# ---------------------------------------------------------------------------
def parse_project_input(path: Path | None = None) -> dict:
    """
    Parse inputs/project_input.md into a structured dict. Tolerant of missing
    sections — returns empty lists/strings rather than raising. NEVER invents
    values: a field absent from the file is absent from the result.

    Returns:
      {
        "business": {"name", "type", "location", "details", "google_url"},
        "design_references": [url, ...],
        "image_references": [url, ...],
        "images_to_generate": [str, ...],
        "must_include": [str, ...],
        "must_avoid": [str, ...],
      }
    """
    path = path or PROJECT_INPUT
    out = {
        "business": {"name": "", "type": "", "location": "", "details": "", "google_url": ""},
        "design_references": [],
        "image_references": [],
        "images_to_generate": [],
        "must_include": [],
        "must_avoid": [],
    }
    if not path.exists():
        return out

    text = path.read_text(encoding="utf-8", errors="ignore")
    section = None
    field_map = {
        "name": "name", "type": "type", "location": "location",
        "details": "details",
    }

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()

        if low.startswith("## "):
            heading = low[3:].strip()
            if heading.startswith("business"):
                section = "business"
            elif heading.startswith("design reference"):
                section = "design_references"
            elif heading.startswith("image reference"):
                section = "image_references"
            elif heading.startswith("images to generate"):
                section = "images_to_generate"
            elif heading.startswith("hard requirement"):
                section = "hard"
            else:
                section = None
            continue

        # bullet line
        item = line
        if item.startswith(("- ", "* ")):
            item = item[2:].strip()
        else:
            continue

        if section == "business":
            # "Key: value" pairs
            if ":" in item:
                k, _, v = item.partition(":")
                k = k.strip().lower()
                v = v.strip()
                if v in ("", "<url if known>"):
                    continue
                if "google" in k or "maps" in k or "business url" in k:
                    out["business"]["google_url"] = v
                else:
                    for token, key in field_map.items():
                        if k.startswith(token):
                            out["business"][key] = v
                            break
        elif section in ("design_references", "image_references"):
            if item.startswith("<") or item.startswith("http") or "." in item:
                if item.startswith("http"):
                    out[section].append(item)
        elif section == "images_to_generate":
            cleaned = item.strip().strip('"').strip()
            if cleaned and not cleaned.startswith("<"):
                out["images_to_generate"].append(cleaned)
        elif section == "hard":
            il = item.lower()
            if il.startswith("must include"):
                val = item.split(":", 1)[1].strip() if ":" in item else ""
                if val and not val.startswith("<"):
                    out["must_include"].append(val)
            elif il.startswith("must avoid"):
                val = item.split(":", 1)[1].strip() if ":" in item else ""
                if val and not val.startswith("<"):
                    out["must_avoid"].append(val)

    return out


def have_module(name: str) -> bool:
    """Check if an importable module is available without importing it fully."""
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def die(msg: str, code: int = 1):
    log(msg, "ERROR")
    sys.exit(code)
