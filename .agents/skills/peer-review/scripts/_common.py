#!/usr/bin/env python3
"""Shared, dependency-free safety helpers for local peer-review CLIs."""

from __future__ import annotations

import csv
import json
import os
import re
import io
import stat
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterable

MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_ROWS = 5_000
MAX_CELL_CHARS = 12_000
MAX_TEXT_CHARS = 50_000
MAX_LIST_ITEMS = 2_000

IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,95}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


class ValidationError(ValueError):
    """A deterministic, user-correctable validation failure."""


def _duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"JSON object contains duplicate key: {key}")
        result[key] = value
    return result


# Project-anchored workspace boundary. Installed layout is mandatory and cannot
# be enlarged with an environment variable or command-line argument.
_SKILL_ROOT = Path(os.path.abspath(__file__)).parent.parent
if (_SKILL_ROOT.name != "peer-review" or _SKILL_ROOT.parent.name != "skills"
        or _SKILL_ROOT.parent.parent.name != ".agents"):
    raise RuntimeError("peer-review must be installed in .agents/skills")
_PROJECT_ROOT = _SKILL_ROOT.parent.parent.parent
_ASSET_FILES = {
    ".agents/skills/peer-review/assets/reporting_guidelines.json",
    ".agents/skills/peer-review/assets/review_scaffold_template.md",
}


def _parts(raw_path: str | Path, *, output: bool = False) -> tuple[str, ...]:
    path = Path(raw_path)
    if ".." in path.parts:
        raise ValidationError("parent traversal is not accepted")
    absolute = path if path.is_absolute() else Path.cwd() / path
    try:
        relative = absolute.relative_to(_PROJECT_ROOT)
    except ValueError as exc:
        raise ValidationError("path must be inside project workspace") from exc
    parts = relative.parts
    asset = relative.as_posix() in _ASSET_FILES
    if not parts or (parts[0] != "workspace" and (output or not asset)):
        raise ValidationError("path must be inside workspace or an allowed read-only asset")
    return parts


@contextmanager
def _parent(raw_path: str | Path, *, output: bool = False):
    if (not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY")
            or os.open not in os.supports_dir_fd):
        raise ValidationError("secure directory-relative operations unavailable")
    parts = _parts(raw_path, output=output)
    fd = None
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        fd = os.open(_PROJECT_ROOT, flags)
        for part in parts[:-1]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd, parts[-1]
    except OSError as exc:
        raise ValidationError("inaccessible, existing, or unsafe path") from exc
    finally:
        if fd is not None:
            os.close(fd)


def _read_text(raw_path: str | Path, suffixes: Iterable[str], *, encoding="utf-8") -> str:
    if Path(raw_path).suffix.lower() not in {s.lower() for s in suffixes}:
        raise ValidationError("invalid input file extension")
    with _parent(raw_path) as (parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValidationError("input must be a non-hard-linked regular file")
            if info.st_size > MAX_INPUT_BYTES:
                raise ValidationError("input exceeds size limit")
            with os.fdopen(fd, "rb") as handle:
                fd = -1
                data = handle.read(MAX_INPUT_BYTES + 1)
            if len(data) > MAX_INPUT_BYTES:
                raise ValidationError("input exceeds size limit")
        finally:
            if fd != -1:
                os.close(fd)
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise ValidationError("input must be UTF-8") from exc


def safe_input_path(raw_path: str | Path, suffixes: Iterable[str]) -> Path:
    # Kept for interface compatibility, not a capability; reads use _read_text.
    _parts(raw_path)
    if Path(raw_path).suffix.lower() not in {s.lower() for s in suffixes}:
        raise ValidationError("invalid input file extension")
    return Path(raw_path)


def safe_output_path(raw_path: str | Path, suffix: str, *, force: bool = False) -> Path:
    if force:
        raise ValidationError("--force is disabled; outputs cannot be overwritten")
    _parts(raw_path, output=True)
    path = Path(raw_path)
    if path.suffix.lower() != suffix.lower():
        raise ValidationError(f"output must use {suffix}")
    return path


def read_json(raw_path: str | Path) -> Any:
    """Read strict UTF-8 JSON with duplicate-key detection."""
    path = Path(raw_path)
    text = _read_text(path, {".json"})
    if "\x00" in text:
        raise ValidationError(f"JSON contains a NUL byte: {path}")
    try:
        return json.loads(text, object_pairs_hook=_duplicate_safe_object)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def read_markdown(raw_path: str | Path) -> str:
    """Read one bounded UTF-8 Markdown file."""
    path = Path(raw_path)
    text = _read_text(path, {".md", ".markdown"})
    if "\x00" in text:
        raise ValidationError(f"Markdown contains a NUL byte: {path}")
    return text


def read_csv_records(
    raw_path: str | Path,
    *,
    required_fields: Iterable[str],
    allowed_fields: Iterable[str] | None = None,
    max_rows: int = MAX_ROWS,
) -> list[dict[str, str]]:
    """Read strict UTF-8 CSV records with bounded, unique cells and headers."""
    path = Path(raw_path)
    content = _read_text(path, {".csv"}, encoding="utf-8-sig")
    required = tuple(required_fields)
    allowed = set(allowed_fields) if allowed_fields is not None else None
    try:
        with io.StringIO(content, newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            if not headers:
                raise ValidationError(f"CSV has no header: {path}")
            normalized = [header.strip() for header in headers]
            if any(not header for header in normalized):
                raise ValidationError("CSV headers must not be blank")
            if len(normalized) != len(set(normalized)):
                raise ValidationError("CSV headers must be unique")
            missing = sorted(set(required) - set(normalized))
            if missing:
                raise ValidationError(
                    f"CSV is missing required columns: {', '.join(missing)}"
                )
            if allowed is not None:
                unknown = sorted(set(normalized) - allowed)
                if unknown:
                    raise ValidationError(
                        f"CSV contains unknown columns: {', '.join(unknown)}"
                    )
            reader.fieldnames = normalized
            records: list[dict[str, str]] = []
            for line_number, row in enumerate(reader, start=2):
                if line_number - 1 > max_rows:
                    raise ValidationError(f"CSV exceeds {max_rows} data rows")
                if None in row:
                    raise ValidationError(
                        f"row {line_number} has more cells than the header"
                    )
                cleaned: dict[str, str] = {}
                for key, value in row.items():
                    cell = "" if value is None else value.strip()
                    if "\x00" in cell:
                        raise ValidationError(
                            f"row {line_number}, column {key} contains a NUL byte"
                        )
                    if len(cell) > MAX_CELL_CHARS:
                        raise ValidationError(
                            f"row {line_number}, column {key} exceeds "
                            f"{MAX_CELL_CHARS} characters"
                        )
                    cleaned[key] = cell
                if any(cleaned.values()):
                    records.append(cleaned)
    except UnicodeDecodeError as exc:
        raise ValidationError(f"CSV must be UTF-8: {path}") from exc
    except csv.Error as exc:
        raise ValidationError(f"invalid CSV: {exc}") from exc
    if not records:
        raise ValidationError("CSV must contain at least one data row")
    return records


def require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{context} must be a JSON object")
    return value


def require_exact_keys(
    value: dict[str, Any],
    *,
    required: Iterable[str],
    optional: Iterable[str] = (),
    context: str,
) -> None:
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        raise ValidationError(f"{context} is missing fields: {', '.join(missing)}")
    if unknown:
        raise ValidationError(f"{context} has unknown fields: {', '.join(unknown)}")


def require_list(
    value: Any,
    context: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_LIST_ITEMS,
) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{context} must be a JSON array")
    if not minimum <= len(value) <= maximum:
        raise ValidationError(
            f"{context} must contain between {minimum} and {maximum} items"
        )
    return value


def require_text(
    value: Any,
    context: str,
    *,
    allow_empty: bool = False,
    minimum: int = 1,
    maximum: int = MAX_TEXT_CHARS,
) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{context} must be a string")
    text = value.strip()
    if not allow_empty and not text:
        raise ValidationError(f"{context} must not be empty")
    if text and len(text) < minimum:
        raise ValidationError(f"{context} must contain at least {minimum} characters")
    if len(text) > maximum:
        raise ValidationError(f"{context} exceeds {maximum} characters")
    if "\x00" in text:
        raise ValidationError(f"{context} contains a NUL byte")
    return text


def require_bool(value: Any, context: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{context} must be true or false")
    return value


def require_enum(value: Any, choices: Iterable[str], context: str) -> str:
    text = require_text(value, context, maximum=96)
    allowed = set(choices)
    if text not in allowed:
        raise ValidationError(
            f"{context} must be one of: {', '.join(sorted(allowed))}"
        )
    return text


def require_identifier(value: Any, context: str) -> str:
    identifier = require_text(value, context, maximum=96)
    if not IDENTIFIER_RE.fullmatch(identifier):
        raise ValidationError(f"{context} has an invalid identifier format")
    return identifier


def require_unique(values: Iterable[str], context: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ValidationError(
            f"{context} contains duplicate IDs: {', '.join(sorted(duplicates))}"
        )


def require_text_list(
    value: Any,
    context: str,
    *,
    minimum: int = 0,
    maximum: int = 100,
) -> list[str]:
    items = require_list(value, context, minimum=minimum, maximum=maximum)
    return [
        require_text(item, f"{context}[{index}]", maximum=500)
        for index, item in enumerate(items)
    ]


def require_identifier_list(
    value: Any,
    context: str,
    *,
    minimum: int = 0,
    maximum: int = 100,
) -> list[str]:
    items = require_list(value, context, minimum=minimum, maximum=maximum)
    parsed = [
        require_identifier(item, f"{context}[{index}]")
        for index, item in enumerate(items)
    ]
    require_unique(parsed, context)
    return parsed


def split_identifiers(
    value: Any, context: str, *, allow_empty: bool = False
) -> list[str]:
    text = require_text(value, context, allow_empty=allow_empty, maximum=MAX_CELL_CHARS)
    if not text:
        return []
    parts = [part.strip() for part in text.split(";")]
    if any(not part for part in parts):
        raise ValidationError(f"{context} contains an empty identifier")
    parsed = [require_identifier(part, context) for part in parts]
    require_unique(parsed, context)
    return parsed


def require_iso_date(value: Any, context: str) -> str:
    text = require_text(value, context, maximum=10)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"{context} must be an ISO date (YYYY-MM-DD)") from exc
    return text


def require_url(value: Any, context: str, *, allow_empty: bool = False) -> str:
    text = require_text(value, context, allow_empty=allow_empty, maximum=2_000)
    if text and not URL_RE.fullmatch(text):
        raise ValidationError(f"{context} must be an http or https URL")
    return text


def require_doi(value: Any, context: str, *, allow_empty: bool = False) -> str:
    text = require_text(value, context, allow_empty=allow_empty, maximum=500)
    if text and not DOI_RE.fullmatch(text):
        raise ValidationError(f"{context} has an invalid DOI format")
    return text


def atomic_write_text(destination: Path, text: str, *, mode: int = 0o600) -> Path:
    """Create exclusively without following links; existing outputs never change."""
    data = text.encode("utf-8")
    if len(data) > MAX_INPUT_BYTES:
        raise ValidationError("output exceeds size limit")
    with _parent(destination, output=True) as (parent, name):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     mode, dir_fd=parent)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    return destination


def write_json_report(
    data: Any, output: str | Path | None, *, force: bool = False
) -> None:
    """Print JSON or exclusively create an explicitly selected local file."""
    if force:
        raise ValidationError("--force is disabled; outputs cannot be overwritten")
    serialized = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output is None:
        print(serialized, end="")
        return
    destination = safe_output_path(output, ".json", force=force)
    atomic_write_text(destination, serialized)


def write_markdown(
    text: str, output: str | Path, *, force: bool = False
) -> Path:
    destination = safe_output_path(output, ".md", force=force)
    return atomic_write_text(destination, text)


def issue(code: str, field: str) -> dict[str, str]:
    """Create a content-free finding safe for confidential reports."""
    return {"code": code, "field": field}


def error_exit(exc: ValidationError) -> int:
    print(f"ERROR: {exc}", file=os.sys.stderr)
    return 2
