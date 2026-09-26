"""Repository walker: safely enumerate source files with ignore rules and limits."""

from __future__ import annotations

import os

from app.parsing.models import SourceFile

# Directories never worth indexing.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "out", "target", "coverage", ".next", ".nuxt",
    ".idea", ".vscode", ".tox", ".nox", "site-packages", ".terraform",
    "vendor", "bower_components", ".cargo", "gradle",
}

# Dotfiles we still want to index (os.path.splitext gives them no extension).
DOTFILE_LANGS = {".env": "env", ".env.local": "env", ".env.example": "env",
                 ".env.development": "env", ".env.production": "env"}

# Extensions we treat as source code (parsed for symbols where supported).
LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".java": "java", ".rb": "ruby", ".rs": "rust",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".php": "php", ".kt": "kotlin", ".swift": "swift",
    ".scala": "scala", ".sh": "shell", ".sql": "sql",
}

# Text files indexed as documentation chunks.
DOC_LANG_BY_EXT = {
    ".md": "markdown", ".rst": "rst", ".txt": "text",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".cfg": "ini", ".ini": "ini", ".env": "env",
}

DEPENDENCY_FILES = {
    "requirements.txt", "requirements-dev.txt", "dev-requirements.txt",
    "pyproject.toml", "setup.py", "Pipfile", "poetry.lock",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "go.mod", "go.sum", "pom.xml", "build.gradle", "Gemfile", "Cargo.toml",
    "composer.json", "Dockerfile", "docker-compose.yml", "Makefile",
}

MAX_FILE_SIZE = 200_000  # bytes per file
MAX_FILES = 6_000  # hard cap on indexed files per repo


def _looks_binary(path: str, chunk: bytes) -> bool:
    if path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
                      ".zip", ".gz", ".tar", ".woff", ".woff2", ".ttf", ".eot",
                      ".mp4", ".mp3", ".wasm", ".so", ".dylib", ".exe", ".bin", ".lock")):
        return True
    return b"\x00" in chunk[:1024]


def walk_repository(root: str) -> list[SourceFile]:
    """Walk a repository root and return SourceFiles for code, docs and config.

    Applies ignore rules, size caps and a hard file limit for safety.
    """
    files: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git"))
        for fname in sorted(filenames):
            if len(files) >= MAX_FILES:
                return files
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            ext = os.path.splitext(fname)[1].lower()
            lang = LANG_BY_EXT.get(ext) or DOC_LANG_BY_EXT.get(ext)
            if lang is None and fname in DOTFILE_LANGS:
                lang = DOTFILE_LANGS[fname]
            if lang is None and fname not in DEPENDENCY_FILES:
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_SIZE:
                    continue
                with open(full, "rb") as fh:
                    head = fh.read(1024)
                    if _looks_binary(fname, head):
                        continue
                    fh.seek(0)
                    raw = fh.read()
            except OSError:
                continue
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception:
                continue
            files.append(SourceFile(path=rel, language=lang, content=text, size=len(raw)))
    return files
