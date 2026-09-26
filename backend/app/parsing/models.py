"""Core data models shared across the RepoPilot pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class SourceFile:
    """A single source file inside a repository."""

    path: str  # repo-relative path, posix style
    language: str  # "python", "typescript", ...
    content: str
    size: int
    lines: int = 0

    def __post_init__(self) -> None:
        self.lines = self.content.count("\n") + 1 if self.content else 0


@dataclass
class ImportRecord:
    """One import statement, resolved against the repository when possible."""

    file: str
    module: str  # raw module text, e.g. "app.services.users"
    names: list[str] = field(default_factory=list)  # imported names
    alias: dict[str, str] = field(default_factory=dict)  # local_name -> original name
    level: int = 0  # relative import level (Python)
    resolved_file: str | None = None  # in-repo file this import points to
    external: bool = False


@dataclass
class Symbol:
    """A code symbol: function, class, method, etc."""

    name: str
    kind: str  # "function" | "class" | "method"
    file: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""
    parent: str | None = None  # enclosing class name for methods
    decorators: list[str] = field(default_factory=list)
    returns_none: bool = False  # explicitly `return None` somewhere in body
    raises: list[str] = field(default_factory=list)

    @property
    def qualified(self) -> str:
        return f"{self.parent}.{self.name}" if self.parent else self.name

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RouteInfo:
    """An HTTP endpoint discovered from decorators (FastAPI/Flask) or framework calls."""

    method: str  # GET/POST/...
    path: str
    handler: str  # handler function name
    file: str
    line: int
    framework: str = "unknown"


@dataclass
class CallEdge:
    """A best-effort resolved call edge between symbols."""

    caller_file: str
    caller_symbol: str
    callee_text: str  # as written, e.g. "user_service.get_user_by_username"
    callee_file: str | None = None
    callee_symbol: str | None = None
    line: int = 0


@dataclass
class RepoSummary:
    """High-level facts about a repository (produced by ingestion/detection)."""

    name: str = ""
    languages: dict[str, int] = field(default_factory=dict)  # language -> file count
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    dir_roles: dict[str, list[str]] = field(default_factory=dict)  # role -> dirs
    file_count: int = 0
    loc: int = 0
    test_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
