"""Shared, dependency-free safety helpers for scientific-writing CLIs."""

from __future__ import annotations

import csv
import io
import json
import os
import stat
import sys
from contextlib import contextmanager
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 5_000_000
MAX_RECORDS = 10_000
MAX_JSON_NODES = 100_000
MAX_JSON_DEPTH = 50
MAX_CSV_FIELD_BYTES = 100_000


class InputError(ValueError):
    """Raised when a local input fails a bounded safety check."""


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    location: str | None = None
    item_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {key: value for key, value in asdict(self).items() if value is not None}


# The installation layout fixes the root; callers cannot enlarge it with a flag
# or environment variable. External material must be explicitly authorized and
# copied into this workspace using Codex's own permissions before invoking a CLI.
_SCRIPT_PATH = Path(__file__).resolve()
_SKILL_ROOT = _SCRIPT_PATH.parent.parent
if (_SKILL_ROOT.name != "scientific-writing" or
        _SKILL_ROOT.parent.name != "skills" or
        _SKILL_ROOT.parent.parent.name != ".agents"):
    raise RuntimeError("scientific-writing must be installed in .agents/skills")
WORKSPACE_ROOT = _SKILL_ROOT.parent.parent.parent


def _relative_parts(path_value: str | Path) -> tuple[str, ...]:
    path = Path(path_value)
    if ".." in path.parts:
        raise InputError("parent path traversal is not accepted")
    absolute = path if path.is_absolute() else Path.cwd() / path
    try:
        relative = absolute.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise InputError("path must be inside the project workspace") from exc
    if not relative.parts:
        raise InputError("path must name an item inside the project workspace")
    return relative.parts


@contextmanager
def _parent_dir(path_value: str | Path):
    """Open every path component without following symlinks, anchored at root."""
    if (not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY") or
            os.open not in os.supports_dir_fd or os.mkdir not in os.supports_dir_fd):
        raise InputError("secure directory-relative file operations are unavailable")
    parts = _relative_parts(path_value)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(WORKSPACE_ROOT, flags)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd, parts[-1]
    finally:
        os.close(fd)


def _check_extension(path_value: str | Path, suffixes: Iterable[str], label: str) -> None:
    allowed = {suffix.lower() for suffix in suffixes}
    if Path(path_value).suffix.lower() not in allowed:
        raise InputError(f"{label} extension must be one of: {', '.join(sorted(allowed))}")


def read_text(path_value: str | Path, suffixes: Iterable[str]) -> str:
    _check_extension(path_value, suffixes, "input")
    with _parent_dir(path_value) as (parent_fd, name):
        # NONBLOCK prevents blocking if a non-regular file is supplied.
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise InputError("input must be an existing regular file")
            if info.st_nlink != 1:
                raise InputError("hard-linked inputs are not accepted")
            if info.st_size > MAX_FILE_BYTES:
                raise InputError(f"input exceeds {MAX_FILE_BYTES} bytes")
            with os.fdopen(fd, "rb") as handle:
                fd = -1
                data = handle.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise InputError(f"input exceeds {MAX_FILE_BYTES} bytes")
        finally:
            if fd != -1:
                os.close(fd)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError("input must be UTF-8 text") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("JSON contains a duplicate object key")
        result[key] = value
    return result


def _reject_nonfinite_json(_value: str) -> None:
    raise InputError("JSON non-finite numbers are not accepted")


def _check_json_bounds(value: Any, depth: int = 0) -> int:
    if depth > MAX_JSON_DEPTH:
        raise InputError(f"JSON nesting exceeds {MAX_JSON_DEPTH} levels")
    count = 1
    if isinstance(value, dict):
        for child in value.values():
            count += _check_json_bounds(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_RECORDS:
            raise InputError(f"JSON array exceeds {MAX_RECORDS} records")
        for child in value:
            count += _check_json_bounds(child, depth + 1)
    if count > MAX_JSON_NODES:
        raise InputError(f"JSON exceeds {MAX_JSON_NODES} nodes")
    return count


def read_json(path_value: str | Path) -> Any:
    text = read_text(path_value, {".json"})
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_json,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise InputError("input is not valid bounded JSON") from exc
    _check_json_bounds(value)
    return value


def read_csv(path_value: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    text = read_text(path_value, {".csv"})
    csv.field_size_limit(MAX_CSV_FIELD_BYTES)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        fields = list(reader.fieldnames or [])
        if not fields or any(not field for field in fields):
            raise InputError("CSV requires a non-empty header row")
        if len(set(fields)) != len(fields):
            raise InputError("CSV contains duplicate header names")
        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader, start=1):
            if index > MAX_RECORDS:
                raise InputError(f"CSV exceeds {MAX_RECORDS} data rows")
            if None in row:
                raise InputError("CSV row has more fields than the header")
            rows.append({key: value or "" for key, value in row.items()})
    except csv.Error as exc:
        raise InputError("input is not valid bounded CSV") from exc
    return fields, rows


def issue(
    severity: str,
    code: str,
    *,
    location: str | None = None,
    item_id: str | None = None,
) -> Issue:
    if severity not in {"error", "warning", "info"}:
        raise ValueError("unsupported issue severity")
    return Issue(severity=severity, code=code, location=location, item_id=item_id)


def emit_report(
    tool: str,
    issues: Iterable[Issue],
    *,
    summary: dict[str, Any] | None = None,
) -> int:
    ordered = sorted(
        issues,
        key=lambda item: (
            {"error": 0, "warning": 1, "info": 2}[item.severity],
            item.code,
            item.location or "",
            item.item_id or "",
        ),
    )
    error_count = sum(item.severity == "error" for item in ordered)
    warning_count = sum(item.severity == "warning" for item in ordered)
    payload = {
        "tool": tool,
        "status": "fail" if error_count else "pass",
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            **(summary or {}),
        },
        "issues": [item.to_dict() for item in ordered],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if error_count else 0


def emit_input_error(tool: str, exc: Exception) -> int:
    return emit_report(
        tool,
        [issue("error", "INVALID_INPUT", location=type(exc).__name__)],
    )


def require_object(value: Any, label: str = "root") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{label} must be a JSON object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"{label} must be a JSON array")
    if len(value) > MAX_RECORDS:
        raise InputError(f"{label} exceeds {MAX_RECORDS} records")
    return value


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_iso_date(value: Any) -> bool:
    """Accept an actual calendar date in the exact YYYY-MM-DD form."""
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def is_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return (
        not lowered
        or "[[todo" in lowered
        or lowered in {"todo", "tbd", "tk", "replace_me", "unknown"}
    )


def create_new_directory(path_value: str | Path) -> None:
    """Create one new directory inside the workspace without following links."""
    with _parent_dir(path_value) as (parent_fd, name):
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)


def write_new_text(
    path_value: str | Path, content: str, suffixes: Iterable[str]
) -> Path:
    path = Path(path_value)
    _check_extension(path, suffixes, "output")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise InputError(f"output exceeds {MAX_FILE_BYTES} bytes")
    with _parent_dir(path) as (parent_fd, name):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent_fd)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
    return path


def main_guard(tool: str, callback: Any) -> int:
    try:
        return int(callback())
    except (InputError, OSError, ValueError) as exc:
        return emit_input_error(tool, exc)


def run(tool: str, callback: Any) -> None:
    raise SystemExit(main_guard(tool, callback))


if __name__ == "__main__":
    print("This module is imported by the scientific-writing command-line tools.")
    sys.exit(0)
