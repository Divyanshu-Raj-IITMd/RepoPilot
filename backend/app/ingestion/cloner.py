"""Clone a remote repository (shallow) or load one from a local path, with guards."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import uuid

_GIT_URL_RE = re.compile(r"^(?:https?://|git@)[^\s]+$")

MAX_CLONE_TIMEOUT = 120  # seconds
MAX_REPO_BYTES = 300 * 1024 * 1024  # refuse to keep indexing beyond 300MB of files


class IngestError(Exception):
    pass


def is_git_url(source: str) -> bool:
    return bool(_GIT_URL_RE.match(source.strip()))


def clone_or_load(source: str, dest_root: str) -> str:
    """Return a local filesystem path for the repository at `source`.

    `source` may be a git URL (shallow-cloned into dest_root) or a local path.
    """
    source = source.strip()
    if is_git_url(source):
        return _clone(source, dest_root)
    path = os.path.abspath(os.path.expanduser(source))
    if not os.path.isdir(path):
        raise IngestError(f"local path is not a directory: {path}")
    return path


log = logging.getLogger("repopilot.cloner")

_CLONE_LOCK = threading.Lock()  # one clone at a time — retries used to race


def _stale_clone_dirs(dest_root: str, slug: str) -> list[str]:
    """Leftover clone directories for this slug (legacy exact name + unique dirs)."""
    if not os.path.isdir(dest_root):
        return []
    return [os.path.join(dest_root, entry) for entry in os.listdir(dest_root)
            if entry == slug or entry.startswith(f"{slug}-")]


def _cleanup_stale(dirs: list[str]) -> None:
    """Best-effort removal of leftover clones — must NEVER block ingestion.

    A locked directory (antivirus, sync client, an orphaned git process) is
    logged and skipped; the next clone simply uses a fresh unique directory,
    so debris can never block ingestion.
    """
    for path in dirs:
        try:
            shutil.rmtree(path)
        except FileNotFoundError:
            pass
        except OSError:
            log.warning("could not remove leftover clone dir (locked, skipping): %s", path)


def _clone(url: str, dest_root: str) -> str:
    """Shallow-clone `url` into a FRESH unique directory under dest_root.

    Design rules (each born from a real-world failure):
      * always clone into `<slug>-<random>` — a locked leftover directory can
        never collide with the clone target, so it can never block ingestion;
      * serialized by a global lock — two ingestion retries used to race each
        other and misread the other's in-flight clone as a locked leftover;
      * git runs with credential prompts disabled — a server-side clone must
        fail fast with a clear error instead of hanging on an invisible
        credential dialog (cached Git Credential Manager creds still work);
      * a failed or timed-out clone removes its own directory — no debris.
    """
    with _CLONE_LOCK:
        os.makedirs(dest_root, exist_ok=True)
        slug = re.sub(r"[^A-Za-z0-9_.-]", "_",
                      url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git"))
        _cleanup_stale(_stale_clone_dirs(dest_root, slug))
        target = os.path.join(dest_root, f"{slug}-{uuid.uuid4().hex[:8]}")
        env = dict(os.environ)
        env.update({
            "GIT_TERMINAL_PROMPT": "0",   # never prompt on the terminal
            "GCM_INTERACTIVE": "never",   # Git Credential Manager: no popups
        })
        try:
            proc = subprocess.run(
                ["git", "clone", "--depth", "1", "--single-branch", url, target],
                capture_output=True, text=True, timeout=MAX_CLONE_TIMEOUT, env=env,
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(target, ignore_errors=True)  # never leave a partial clone
            raise IngestError(f"git clone timed out after {MAX_CLONE_TIMEOUT}s") from exc
        if proc.returncode != 0:
            shutil.rmtree(target, ignore_errors=True)  # never leave a partial clone
            err = proc.stderr.strip()[:400]
            if re.search(r"could not read [Uu]sername|[Aa]uthentication failed", err):
                err += (" — private repository? HTTPS clones need credentials: use Git "
                        "Credential Manager, embed a Personal Access Token in the URL, or "
                        "clone locally and add the repo by path instead.")
            raise IngestError(f"git clone failed: {err}")
        return target


def repo_size_bytes(root: str) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".venv")]
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def snapshot_repo_files(root: str) -> None:
    """No-op placeholder kept for API symmetry (streaming, not copying, is used)."""
    return None
