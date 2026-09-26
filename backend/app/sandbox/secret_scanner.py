"""Security: secret scanning + redaction before any content reaches an LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.parsing.models import SourceFile

# High-signal secret patterns (deliberately conservative to limit false positives).
SECRET_PATTERNS: list[tuple[str, str, str]] = [
    ("aws_access_key", "AWS access key", r"AKIA[0-9A-Z]{16}"),
    ("google_api_key", "Google API key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("private_key", "Private key block", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("github_token", "GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("slack_token", "Slack token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ("db_url_password", "Database URL with password", r"\b(?:postgres|postgresql|mysql|mongodb(\+srv)?|redis|amqp)://[^\s:]+:[^\s:@]+@"),
    ("assigned_secret", "Hardcoded secret assignment",
     r"(?i)\b\w*(?:secret|api_?key|apikey|passwo?rd|pwd|token|private_?key|credential)\w*\b\s*[=:]\s*[\"'][^\"'\s]{8,}[\"']"),
]

REDACTABLE_EXTS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs",
                   ".json", ".yaml", ".yml", ".toml", ".env", ".cfg", ".ini", ".txt", ".md",
                   ".sh", ".sql", ".c", ".cpp", ".h"}

_BUT_NOT_ENV = re.compile(r"os\.environ|getenv|process\.env|settings\.", re.I)


@dataclass
class SecurityFinding:
    kind: str
    title: str
    file: str
    line: int
    match: str  # truncated

    def to_dict(self) -> dict:
        return {"kind": self.kind, "title": self.title, "file": self.file,
                "line": self.line, "match": self.match}


@dataclass
class SecurityScan:
    findings: list[SecurityFinding] = field(default_factory=list)

    @property
    def has_blocking(self) -> bool:
        return any(f.kind in ("aws_access_key", "private_key", "github_token",
                              "google_api_key", "slack_token", "db_url_password")
                   for f in self.findings)

    def summary(self) -> dict:
        by_kind: dict[str, int] = {}
        for f in self.findings:
            by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
        return {"count": len(self.findings), "by_kind": by_kind,
                "files": sorted({f.file for f in self.findings})}


def scan_files(files: list[SourceFile]) -> SecurityScan:
    scan = SecurityScan()
    for sf in files:
        if sf.language in ("markdown", "rst") or "test" in sf.path:
            continue  # docs & tests often show example keys; still scan code/config
        for i, line in enumerate(sf.content.splitlines(), start=1):
            for kind, title, pattern in SECRET_PATTERNS:
                m = re.search(pattern, line)
                if not m:
                    continue
                if kind == "assigned_secret" and _BUT_NOT_ENV.search(line):
                    continue
                scan.findings.append(SecurityFinding(
                    kind=kind, title=title, file=sf.path, line=i,
                    match=m.group(0)[:60],
                ))
    return scan


def redact(text: str) -> str:
    """Redact secret-looking spans before sending content to any LLM."""
    def _sub(m: re.Match) -> str:
        return m.group(0)[:10] + "***REDACTED***"
    out = text
    for _, _, pattern in SECRET_PATTERNS:
        out = re.sub(pattern, _sub, out)
    return out
