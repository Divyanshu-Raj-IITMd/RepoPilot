"""Language, framework, database and entry-point detection for an indexed repository."""

from __future__ import annotations

import re
from collections import Counter

from app.parsing.models import RepoSummary, SourceFile

# (framework, marker regexes over file content, languages it applies to)
_FRAMEWORK_MARKERS: list[tuple[str, list[str]]] = [
    ("FastAPI", [r"\bfrom fastapi\b", r"\bimport fastapi\b", r"fastapi[>=<]"]),
    ("Flask", [r"\bfrom flask\b", r"\bFlask\(__name__\)"]),
    ("Django", [r"\bfrom django\b", r"django[>=<]"]),
    ("Starlette", [r"\bfrom starlette\b"]),
    ("SQLAlchemy", [r"\bfrom sqlalchemy\b", r"sqlalchemy[>=<]"]),
    ("Pydantic", [r"\bfrom pydantic\b"]),
    ("Pytest", [r"\bimport pytest\b", r"pytest[>=<]"]),
    ("Requests", [r"\bimport requests\b"]),
    ("Celery", [r"\bfrom celery\b"]),
    ("PyTorch", [r"\bimport torch\b"]),
    ("TensorFlow", [r"\bimport tensorflow\b"]),
    ("scikit-learn", [r"\bfrom sklearn\b", r"scikit-learn[>=<]"]),
    ("Next.js", [r'"next"']),
    ("React", [r'\bfrom ["\']react["\']', r'"react"']),
    ("Vue", [r'\bfrom ["\']vue["\']', r'"vue"']),
    ("Svelte", [r'\bfrom ["\']svelte["\']']),
    ("Angular", [r'"@angular/core"']),
    ("Express", [r"\brequire\(['\"]express['\"]\)", r"\bfrom ['\"]express['\"]"]),
    ("NestJS", [r'"@nestjs/core"']),
    ("TypeScript", [r'"typescript"']),
    ("Tailwind CSS", [r'"tailwindcss"']),
    ("Prisma", [r'"prisma"', r"\bfrom prisma\b", r"prisma[>=<]"]),
    ("Jest", [r'"jest"']),
    ("Vitest", [r'"vitest"']),
    ("Gin", [r'"github.com/gin-gonic/gin"']),
    ("Echo", [r'"github.com/labstack/echo"']),
    ("Spring Boot", [r"org\.springframework\.boot"]),
    ("Rails", [r"\bgem ['\"]rails['\"]"]),
    ("Actix", [r"actix_web"]),
    ("Axum", [r"\baxum\b"]),
]

_DB_MARKERS: list[tuple[str, list[str]]] = [
    ("SQLite", [r"\bsqlite3\b", r'"sqlite3"', r"sqlite://"]),
    ("PostgreSQL", [r"\bpsycopg", r"postgresql://", r'"pg"']),
    ("MySQL", [r"pymysql|mysqlclient|mysql://", r'"mysql2"']),
    ("MongoDB", [r"\bpymongo\b|mongodb://", r'"mongoose"', r'"mongodb"']),
    ("Redis", [r"\bimport redis\b|redis://", r'"redis"', r'"ioredis"']),
    ("Prisma", [r'"prisma"']),
]

_ENTRY_CANDIDATES = [
    "app/main.py", "src/main.py", "main.py", "app.py", "server.py", "manage.py",
    "run.py", "wsgi.py", "asgi.py", "index.js", "server.js", "src/index.js",
    "src/index.ts", "src/main.ts", "main.ts", "main.go", "cmd/main.go",
    "Program.cs", "src/Application.java",
]

_DIR_ROLE_RULES: list[tuple[str, list[str]]] = [
    ("authentication", ["auth", "authentication", "security", "identity"]),
    ("api", ["routes", "routers", "api", "endpoints", "controllers", "views", "handlers"]),
    ("business logic", ["services", "business", "core", "domain", "usecases", "use_cases", "logic"]),
    ("models", ["models", "entities", "schemas"]),
    ("data access", ["repositories", "repository", "db", "database", "data", "storage", "dal"]),
    ("middleware", ["middleware", "middlewares", "interceptors", "filters"]),
    ("utilities", ["utils", "helpers", "common", "lib", "shared"]),
]


def _match_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def detect_summary(name: str, files: list[SourceFile]) -> RepoSummary:
    """Compute a RepoSummary: languages, frameworks, DBs, entry points, dir roles."""
    summary = RepoSummary(name=name)
    lang_counter: Counter[str] = Counter()
    dep_texts: list[str] = []
    code_text_parts: list[str] = []
    paths = {f.path for f in files}

    for f in files:
        if f.language in LANG_LANGS:
            lang_counter[f.language] += 1
        base = f.path.rsplit("/", 1)[-1]
        if base in DEPENDENCY_FILE_NAMES or f.path.count("/") == 0 and base.startswith(("requirements", "Pipfile")):
            dep_texts.append(f.content[:20_000])
        if f.language in ("python", "javascript", "typescript"):
            code_text_parts.append(f.content[:60_000])
    summary.languages = dict(lang_counter.most_common())
    summary.file_count = len(files)
    summary.loc = sum(f.lines for f in files)
    summary.test_files = sorted(
        f.path for f in files
        if f.path.rsplit("/", 1)[-1].startswith(("test_", "test.")) or "/tests/" in f"/{f.path}" or "__tests__" in f.path
    )

    haystack = "\n".join(dep_texts + code_text_parts)
    seen: set[str] = set()
    for framework, patterns in _FRAMEWORK_MARKERS:
        if framework not in seen and _match_any(patterns, haystack):
            seen.add(framework)
            summary.frameworks.append(framework)
    seen.clear()
    for db, patterns in _DB_MARKERS:
        if db not in seen and _match_any(patterns, haystack):
            seen.add(db)
            summary.databases.append(db)

    summary.entry_points = [p for p in _ENTRY_CANDIDATES if p in paths]

    dirs = sorted({f.path.rsplit("/", 1)[0] for f in files if "/" in f.path})
    for role, keywords in _DIR_ROLE_RULES:
        matched = [
            d for d in dirs
            if any(part == kw or part.startswith(kw) for part in d.split("/") for kw in keywords)
        ]
        if matched:
            summary.dir_roles[role] = matched[:6]
    return summary


LANG_LANGS = {"python", "javascript", "typescript", "go", "java", "rb", "rust",
              "c", "cpp", "csharp", "php", "kt", "swift", "scala"}

DEPENDENCY_FILE_NAMES = {
    "requirements.txt", "requirements-dev.txt", "dev-requirements.txt", "pyproject.toml",
    "setup.py", "Pipfile", "package.json", "go.mod", "pom.xml", "build.gradle",
    "Gemfile", "Cargo.toml", "composer.json",
}
